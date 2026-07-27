//! Simple backend capability surface for the web UI.

use crate::state::AppState;
use axum::{extract::State, Json};
use serde_json::{json, Value};
use std::sync::Arc;

pub async fn capabilities(State(st): State<Arc<AppState>>) -> Json<Value> {
    let helper_ok = st.helper.health().await.is_ok();
    let mut deferred = vec!["image_edits", "estuary_download"];
    if !st.image_enabled {
        deferred.insert(0, "image_generations");
    }
    Json(json!({
        "ok": true,
        "service": "gptimage-gateway-rs",
        "wave": "local-full",
        "helper_ok": helper_ok,
        "features": {
            "auth": !st.auth.config().auth_disabled(),
            "auth_mode": st.auth.config().mode.as_str(),
            "chat": true,
            "chat_stream": true,
            "models": true,
            "quota_probe": true,
            "account_candidates": true,
            "image_generations": st.image_enabled,
            "image_edits": false,
            "estuary_download": false,
            "static_ui": st.static_dir.is_some(),
        },
        "deferred": deferred,
        "notes": {
            "image": if st.image_enabled {
                "IMAGE_ENABLED=1 — generations routed to helper"
            } else {
                "Set IMAGE_ENABLED=1 to enable /v1/images/generations"
            },
            "local": "bash scripts/local_bringup_wsl.sh (LOCAL_MODE=full default)"
        }
    }))
}

/// Full runtime detail. Admin-only: exposes pool identities and tuning that
/// the unauthenticated `/health` deliberately omits.
pub async fn admin_status(State(st): State<Arc<AppState>>) -> Json<Value> {
    let accounts = st.accounts.lock().await;
    let emails: Vec<&str> = accounts.keys().map(String::as_str).collect();
    Json(json!({
        "ok": true,
        "listen": st.listen,
        "pin_email": st.pin.email,
        "accounts": emails,
        "image_global_concurrency": st.image_global_concurrency,
        "image_sem_available": st.image_sem.available_permits(),
        "min_image_quota": st.min_image_quota,
        "image_enabled": st.image_enabled,
        "auth_disabled": st.auth.config().auth_disabled(),
        "auth_mode": st.auth.config().mode.as_str(),
        "static_ui": st.static_dir.is_some(),
    }))
}
