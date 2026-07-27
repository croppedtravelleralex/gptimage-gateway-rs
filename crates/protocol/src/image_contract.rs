//! Phase B image/edit/estuary contract shapes (fixtures + future backend).

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use uuid::Uuid;

#[derive(Debug, Clone, Deserialize)]
pub struct ImageEditRequest {
    #[serde(default = "default_image_model")]
    pub model: String,
    pub prompt: String,
    #[serde(default)]
    pub image: Option<String>,
    #[serde(default = "default_n")]
    pub n: u32,
    #[serde(default = "default_size")]
    pub size: String,
}

fn default_image_model() -> String {
    "gpt-image-2".into()
}
fn default_n() -> u32 {
    1
}
fn default_size() -> String {
    "1024x1024".into()
}

/// Stable prepare body fields aligned with gptimage `build_image_prepare_body` (picture_v2).
pub fn build_image_prepare_body(prompt: &str, model_slug: &str) -> Value {
    json!({
        "action": "next",
        "parent_message_id": "client-created-root",
        "model": model_slug,
        "client_prepare_state": "sent",
        "client_prepare_dispatch": "immediate",
        "client_prepare_source": "context_change",
        "timezone_offset_min": -480,
        "timezone": "Asia/Shanghai",
        "conversation_mode": { "kind": "primary_assistant" },
        "system_hints": ["picture_v2"],
        "partial_query": {
            "id": new_uuid(),
            "author": { "role": "user" },
            "content": { "content_type": "text", "parts": ["Create image"] },
        },
        "supports_buffering": true,
        "supported_encodings": ["v1"],
        "client_contextual_info": {
            "app_name": "chatgpt.com",
            "app_version": "fixture",
        },
        "_fixture_prompt": prompt,
    })
}

/// Start body without reference images.
pub fn build_image_start_body(prompt: &str, model_slug: &str) -> Value {
    json!({
        "action": "next",
        "messages": [{
            "id": new_uuid(),
            "author": { "role": "user" },
            "content": { "content_type": "text", "parts": [prompt] },
            "metadata": {
                "system_hints": ["picture_v2"],
                "serialization_metadata": { "custom_symbol_offsets": [] },
            },
        }],
        "parent_message_id": "client-created-root",
        "model": model_slug,
        "client_prepare_state": "none",
        "timezone_offset_min": -480,
        "timezone": "Asia/Shanghai",
        "conversation_mode": { "kind": "primary_assistant" },
        "enable_message_followups": true,
        "system_hints": ["picture_v2"],
        "supports_buffering": true,
        "supported_encodings": ["v1"],
    })
}

/// Start body with multimodal refs (edit path).
pub fn build_image_start_body_with_refs(
    prompt: &str,
    model_slug: &str,
    refs: &[ImageRef],
) -> Value {
    let mut parts: Vec<Value> = refs
        .iter()
        .map(|r| {
            json!({
                "content_type": "image_asset_pointer",
                "asset_pointer": format!("file-service://{}", r.file_id),
                "width": r.width,
                "height": r.height,
                "size_bytes": r.file_size,
            })
        })
        .collect();
    parts.push(json!(prompt));
    json!({
        "action": "next",
        "messages": [{
            "id": new_uuid(),
            "author": { "role": "user" },
            "content": { "content_type": "multimodal_text", "parts": parts },
            "metadata": {
                "system_hints": ["picture_v2"],
                "serialization_metadata": { "custom_symbol_offsets": [] },
                "attachments": refs.iter().map(|r| json!({
                    "id": r.file_id,
                    "mimeType": r.mime_type,
                    "name": r.file_name,
                    "size": r.file_size,
                    "width": r.width,
                    "height": r.height,
                })).collect::<Vec<_>>(),
            },
        }],
        "parent_message_id": "client-created-root",
        "model": model_slug,
        "client_prepare_state": "none",
        "timezone_offset_min": -480,
        "timezone": "Asia/Shanghai",
        "conversation_mode": { "kind": "primary_assistant" },
        "enable_message_followups": true,
        "system_hints": ["picture_v2"],
        "supports_buffering": true,
        "supported_encodings": ["v1"],
    })
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageRef {
    pub file_id: String,
    pub mime_type: String,
    pub file_name: String,
    pub file_size: u64,
    pub width: u32,
    pub height: u32,
}

/// Estuary download must use API session Bearer (never resource session).
pub fn build_estuary_download_headers(access_token: &str) -> Value {
    json!({
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Authorization": format!("Bearer {access_token}"),
    })
}

/// Returns error message if headers violate estuary contract.
pub fn validate_estuary_headers(headers: &Value) -> Result<(), &'static str> {
    let auth = headers
        .get("Authorization")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if !auth.starts_with("Bearer ") {
        return Err("estuary requires Bearer Authorization on API session");
    }
    let token = auth.trim_start_matches("Bearer ").trim();
    if token.is_empty() || token == "REDACTED" {
        // fixture tokens are redacted placeholders — structure check only
        if token.is_empty() {
            return Err("estuary requires non-empty Bearer token");
        }
    }
    Ok(())
}

/// Resource PUT must not carry Bearer/OAI headers.
pub fn validate_resource_put_headers(headers: &Value) -> Result<(), &'static str> {
    for key in ["Authorization", "OAI-Device-Id", "OAI-Language"] {
        if headers.get(key).is_some() {
            return Err("resource PUT must not include API session headers");
        }
    }
    Ok(())
}

/// Fresh message id. Bodies must not ship a fixed literal — the upstream
/// dedupes on it, so a constant makes every request look like a replay.
pub fn new_uuid() -> String {
    Uuid::new_v4().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn message_ids_are_unique_per_build() {
        // A fixed literal id reads as a replay of the same turn upstream.
        let a = build_image_start_body("p", "gpt-image-2");
        let b = build_image_start_body("p", "gpt-image-2");
        assert_ne!(a["messages"][0]["id"], b["messages"][0]["id"]);

        let pa = build_image_prepare_body("p", "gpt-image-2");
        let pb = build_image_prepare_body("p", "gpt-image-2");
        assert_ne!(pa["partial_query"]["id"], pb["partial_query"]["id"]);
    }

    #[test]
    fn estuary_requires_bearer() {
        let ok = build_estuary_download_headers("REDACTED_TOKEN_VALUE");
        assert!(validate_estuary_headers(&ok).is_ok());
        assert!(validate_estuary_headers(&json!({})).is_err());
    }

    #[test]
    fn resource_put_rejects_bearer() {
        assert!(validate_resource_put_headers(&json!({"Content-Type":"image/png"})).is_ok());
        assert!(validate_resource_put_headers(&json!({"Authorization":"Bearer x"})).is_err());
    }
}
