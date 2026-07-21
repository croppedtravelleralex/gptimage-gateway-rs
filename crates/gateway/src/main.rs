//! gptimage-gateway-rs MVP gateway (Rust face).
//!
//! OpenAI-compatible surface; protocol execution via Python curl_cffi bridge
//! (`PROTO_BRIDGE`). Image concurrency is gated here with a process semaphore
//! so conc=1 and conc=3 both target ~40–60s per image (parallel wall ≈ single).

mod config;

use anyhow::Context;
use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use helper_client::{
    HelperClient, ImageRunRequest, PinAccount, QuotaRefreshRequest, TextRunRequest,
};
use protocol::{
    chat_completion_response, image_generation_response, openai_error, ChatCompletionRequest,
    ImageGenerationRequest,
};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::{Mutex, Semaphore};
use tower_http::trace::TraceLayer;
use tracing::{error, info, warn};

#[derive(Clone)]
struct AppState {
    helper: HelperClient,
    pin: PinAccount,
    accounts: Arc<Mutex<HashMap<String, PinAccount>>>,
    listen: String,
    min_image_quota: i64,
    image_global_concurrency: usize,
    image_sem: Arc<Semaphore>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "gateway=info,tower_http=info".into()),
        )
        .init();

    let cfg = config::load().context("load config")?;
    let helper = HelperClient::new(&cfg.helper_url)?;
    match helper.health().await {
        Ok(h) => info!(?h, "helper healthy"),
        Err(e) => tracing::warn!(error=%e, "helper health check failed (will retry on request)"),
    }

    // Seed accounts from helper candidates (unique proxy) when available.
    let mut accounts = cfg.accounts;
    match helper.list_candidates(12).await {
        Ok(cands) => {
            for a in cands {
                accounts.insert(a.email.to_lowercase(), a);
            }
            info!(n = accounts.len(), "accounts ready (pin + helper candidates)");
        }
        Err(e) => warn!(error=%e, "helper candidates unavailable; using pin/ACCOUNTS_FILE only"),
    }

    let state = Arc::new(AppState {
        helper,
        pin: cfg.account,
        accounts: Arc::new(Mutex::new(accounts)),
        listen: cfg.listen.clone(),
        min_image_quota: cfg.min_image_quota,
        image_global_concurrency: cfg.image_global_concurrency,
        image_sem: cfg.image_sem,
    });

    let app = Router::new()
        .route("/health", get(health))
        .route("/v1/models", get(models))
        .route("/v1/accounts/candidates", get(account_candidates))
        .route("/v1/quota", get(quota_refresh))
        .route("/v1/quota/refresh", post(quota_refresh))
        .route("/v1/chat/completions", post(chat_completions))
        .route("/v1/images/generations", post(image_generations))
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(&cfg.listen)
        .await
        .with_context(|| format!("bind {}", cfg.listen))?;
    info!(
        listen=%cfg.listen,
        helper=%cfg.helper_url,
        email=%cfg.account_email_log,
        image_global_concurrency=%cfg.image_global_concurrency,
        "gateway listening (rust)"
    );
    axum::serve(listener, app).await?;
    Ok(())
}

async fn health(State(st): State<Arc<AppState>>) -> impl IntoResponse {
    let helper_ok = st.helper.health().await.is_ok();
    let n_accounts = st.accounts.lock().await.len();
    Json(json!({
        "ok": true,
        "service": "gptimage-gateway-rs",
        "wave": "mvp",
        "runtime": "rust",
        "proto_bridge": true,
        "helper_ok": helper_ok,
        "listen": st.listen,
        "pin_email": st.pin.email,
        "multi_account": true,
        "accounts": n_accounts,
        "image_global_concurrency": st.image_global_concurrency,
        "min_image_quota": st.min_image_quota,
    }))
}

async fn models() -> impl IntoResponse {
    Json(json!({
        "object": "list",
        "data": [
            { "id": "gpt-4o-mini", "object": "model", "owned_by": "gptimage-gateway-rs" },
            { "id": "gpt-image-2", "object": "model", "owned_by": "gptimage-gateway-rs" }
        ]
    }))
}

async fn account_candidates(State(st): State<Arc<AppState>>) -> impl IntoResponse {
    match st.helper.list_candidates(20).await {
        Ok(list) => {
            let mut guard = st.accounts.lock().await;
            for a in &list {
                guard.insert(a.email.to_lowercase(), a.clone());
            }
            let accounts: Vec<Value> = list
                .into_iter()
                .map(|a| {
                    json!({
                        "email": a.email,
                        "proxy_host": a.proxy.as_deref().and_then(|p| p.split('@').next_back()).unwrap_or(""),
                        "has_token": !a.access_token.is_empty(),
                    })
                })
                .collect();
            Json(json!({"ok": true, "count": accounts.len(), "accounts": accounts})).into_response()
        }
        Err(e) => err(
            StatusCode::BAD_GATEWAY,
            e.to_string(),
            "candidates_failed",
            Some("self"),
        ),
    }
}

async fn resolve_account(st: &AppState, preferred: Option<String>) -> Result<PinAccount, axum::response::Response> {
    let email = preferred
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| st.pin.email.clone());
    let key = email.to_lowercase();
    if let Some(acc) = st.accounts.lock().await.get(&key).cloned() {
        return Ok(acc);
    }
    // Refresh candidates once, then retry.
    if let Ok(list) = st.helper.list_candidates(30).await {
        let mut guard = st.accounts.lock().await;
        for a in list {
            guard.insert(a.email.to_lowercase(), a);
        }
        if let Some(acc) = guard.get(&key).cloned() {
            return Ok(acc);
        }
    }
    // Sticky email-only stub — helper pool_sticky resolves token by email.
    Ok(PinAccount {
        email,
        access_token: String::new(),
        device_id: None,
        proxy: None,
        user_agent: None,
    })
}

async fn quota_refresh(
    State(st): State<Arc<AppState>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let preferred = preferred_email(&headers);
    let account = match resolve_account(&st, preferred).await {
        Ok(a) => a,
        Err(r) => return r,
    };
    let req = QuotaRefreshRequest {
        account,
        min_remaining: st.min_image_quota,
    };
    match st.helper.refresh_quota(&req).await {
        Ok(q) if q.ok => (
            StatusCode::OK,
            Json(json!({
                "ok": true,
                "email": q.email,
                "plan": q.plan,
                "status": q.status,
                "remaining": q.remaining,
                "restore_at": q.restore_at,
                "image_quota_unknown": q.image_quota_unknown,
                "min_remaining": q.min_remaining.unwrap_or(st.min_image_quota),
                "imageable": q.imageable.unwrap_or(false),
                "image_gen": q.image_gen,
                "elapsed_ms": q.elapsed_ms,
            })),
        )
            .into_response(),
        Ok(q) => {
            let fault = q.fault.as_deref().unwrap_or("upstream");
            let msg = q.error.unwrap_or_else(|| "quota refresh failed".into());
            let code = if fault == "self" {
                StatusCode::INTERNAL_SERVER_ERROR
            } else {
                StatusCode::BAD_GATEWAY
            };
            err(code, msg, "quota_refresh_failed", Some(fault))
        }
        Err(e) => {
            error!(error=%e, "helper quota call failed");
            err(
                StatusCode::BAD_GATEWAY,
                e.to_string(),
                "helper_unreachable",
                Some("self"),
            )
        }
    }
}

async fn chat_completions(
    State(st): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<ChatCompletionRequest>,
) -> impl IntoResponse {
    if req.stream {
        return err(
            StatusCode::BAD_REQUEST,
            "stream not supported in MVP",
            "stream_unsupported",
            Some("self"),
        );
    }
    let prompt = req
        .messages
        .iter()
        .rev()
        .find(|m| m.role == "user")
        .map(|m| m.text())
        .unwrap_or_default();
    if prompt.trim().is_empty() {
        return err(
            StatusCode::BAD_REQUEST,
            "messages must include a user text",
            "invalid_request",
            Some("self"),
        );
    }

    let account = match resolve_account(&st, preferred_email(&headers)).await {
        Ok(a) => a,
        Err(r) => return r,
    };

    let bridge_req = TextRunRequest {
        account,
        prompt,
        model: req.model.clone(),
    };
    match st.helper.run_text(&bridge_req).await {
        Ok(r) if r.ok => {
            let content = r.content.unwrap_or_default();
            (StatusCode::OK, Json(chat_completion_response(&req.model, &content))).into_response()
        }
        Ok(r) => {
            let fault = r.fault.as_deref().unwrap_or("upstream");
            let msg = r.error.unwrap_or_else(|| "text bridge failed".into());
            let code = if fault == "self" {
                StatusCode::INTERNAL_SERVER_ERROR
            } else {
                StatusCode::BAD_GATEWAY
            };
            err(code, msg, "text_failed", Some(fault))
        }
        Err(e) => {
            error!(error=%e, "helper text call failed");
            err(
                StatusCode::BAD_GATEWAY,
                e.to_string(),
                "helper_unreachable",
                Some("self"),
            )
        }
    }
}

async fn image_generations(
    State(st): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<ImageGenerationRequest>,
) -> impl IntoResponse {
    if req.n != 1 {
        return err(
            StatusCode::BAD_REQUEST,
            "MVP only supports n=1",
            "n_unsupported",
            Some("self"),
        );
    }

    let account = match resolve_account(&st, preferred_email(&headers)).await {
        Ok(a) => a,
        Err(r) => return r,
    };

    // Process-wide image concurrency (default 3). Conc=1 and conc=3 share the same
    // per-image latency target (~40–60s); wall clock scales with available permits.
    let permit = match st.image_sem.clone().acquire_owned().await {
        Ok(p) => p,
        Err(_) => {
            return err(
                StatusCode::SERVICE_UNAVAILABLE,
                "image semaphore closed",
                "semaphore_closed",
                Some("self"),
            );
        }
    };

    // Quota gate on the resolved account (helper also pool-gates).
    let qreq = QuotaRefreshRequest {
        account: account.clone(),
        min_remaining: st.min_image_quota,
    };
    match st.helper.refresh_quota(&qreq).await {
        Ok(q) if q.ok && q.imageable.unwrap_or(false) => {}
        Ok(q) if q.ok => {
            drop(permit);
            return err(
                StatusCode::TOO_MANY_REQUESTS,
                format!(
                    "image_quota_insufficient: remaining={:?} status={:?} min={} restore_at={:?}",
                    q.remaining, q.status, st.min_image_quota, q.restore_at
                ),
                "image_quota_insufficient",
                Some("quota"),
            );
        }
        Ok(q) => {
            drop(permit);
            let fault = q.fault.as_deref().unwrap_or("upstream");
            let msg = q
                .error
                .unwrap_or_else(|| "quota refresh failed before image".into());
            let code = if fault == "self" {
                StatusCode::INTERNAL_SERVER_ERROR
            } else {
                StatusCode::BAD_GATEWAY
            };
            return err(code, msg, "quota_refresh_failed", Some(fault));
        }
        Err(e) => {
            drop(permit);
            error!(error=%e, "helper quota precheck failed");
            return err(
                StatusCode::BAD_GATEWAY,
                e.to_string(),
                "helper_unreachable",
                Some("self"),
            );
        }
    }

    let bridge_req = ImageRunRequest {
        account: account.clone(),
        prompt: req.prompt.clone(),
        model: req.model.clone(),
        size: req.size.clone(),
    };
    let t0 = Instant::now();
    let result = st.helper.run_image(&bridge_req).await;
    let elapsed_ms = t0.elapsed().as_millis();
    drop(permit);

    match result {
        Ok(r) if r.ok => {
            let b64 = r.b64_json.unwrap_or_default();
            if b64.len() < 1000 {
                return err(
                    StatusCode::BAD_GATEWAY,
                    "empty/short b64_json from bridge",
                    "empty_image",
                    Some("self"),
                );
            }
            info!(
                email=%account.email,
                elapsed_ms,
                b64_len=b64.len(),
                "image ok"
            );
            (StatusCode::OK, Json(image_generation_response(&b64))).into_response()
        }
        Ok(r) => {
            let fault = r.fault.as_deref().unwrap_or("upstream");
            let msg = r.error.unwrap_or_else(|| "image bridge failed".into());
            warn!(email=%account.email, elapsed_ms, fault=%fault, error=%msg, "image failed");
            let (code, err_code) = match fault {
                "self" => (StatusCode::INTERNAL_SERVER_ERROR, "image_failed"),
                "quota" => (StatusCode::TOO_MANY_REQUESTS, "image_quota_insufficient"),
                _ => (StatusCode::BAD_GATEWAY, "image_failed"),
            };
            err(code, msg, err_code, Some(fault))
        }
        Err(e) => {
            error!(email=%account.email, elapsed_ms, error=%e, "helper image call failed");
            err(
                StatusCode::BAD_GATEWAY,
                e.to_string(),
                "helper_unreachable",
                Some("self"),
            )
        }
    }
}

fn preferred_email(headers: &HeaderMap) -> Option<String> {
    headers
        .get("x-preferred-account-email")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

fn err(
    status: StatusCode,
    message: impl Into<String>,
    code: &str,
    fault: Option<&str>,
) -> axum::response::Response {
    let body: Value = openai_error(message, code, fault);
    (status, Json(body)).into_response()
}
