//! Simple backend capability surface for the web UI.

use crate::state::AppState;
use axum::{extract::State, Json};
use serde_json::{json, Value};
use std::sync::Arc;

pub async fn capabilities(State(st): State<Arc<AppState>>) -> Json<Value> {
    let helper_ok = st.helper.health().await.is_ok();
    Json(json!({
        "ok": true,
        "service": "gptimage-gateway-rs",
        "wave": "phase-b-lite",
        "helper_ok": helper_ok,
        "features": {
            "auth": !st.auth.config().disabled,
            "chat": true,
            "chat_stream": true,
            "models": true,
            "quota_probe": true,
            "account_candidates": true,
            "image_generations": st.image_enabled,
            "image_edits": false,
            "estuary_download": false,
        },
        "deferred": [
            "image_generations",
            "image_edits",
            "estuary_download"
        ],
        "notes": {
            "image": "Set IMAGE_ENABLED=1 after backend pipeline integration",
            "phase_b": "edits/estuary contract in fixtures + protocol crate"
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
        "auth_disabled": st.auth.config().disabled,
        "static_ui": st.static_dir.is_some(),
    }))
}
