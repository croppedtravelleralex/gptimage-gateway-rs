//! Golden fixture diff tests for protocol shapes.

use protocol::{
    build_estuary_download_headers, build_image_prepare_body, build_image_start_body,
    build_image_start_body_with_refs, build_text_conversation_body, validate_estuary_headers,
    validate_resource_put_headers, ImageRef,
};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;

fn fixture_path(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../fixtures/protocol")
        .join(name)
}

fn load_json(name: &str) -> Value {
    let raw = fs::read_to_string(fixture_path(name)).expect("read fixture");
    serde_json::from_str(&raw).expect("parse fixture json")
}

const STABLE_KEYS: &[&str] = &[
    "action",
    "model",
    "timezone_offset_min",
    "timezone",
    "conversation_mode",
    "system_hints",
    "supports_buffering",
    "supported_encodings",
];

fn assert_stable_keys(built: &Value, golden: &Value) {
    for key in STABLE_KEYS {
        assert_eq!(built.get(key), golden.get(key), "field {key}");
    }
}

#[test]
fn chat_body_matches_fixture() {
    let built = build_text_conversation_body("hello fixture", "gpt-4o-mini");
    let golden = load_json("chat_body.json");
    for key in [
        "action",
        "model",
        "timezone_offset_min",
        "history_and_training_disabled",
        "conversation_mode",
    ] {
        assert_eq!(built.get(key), golden.get(key), "field {key}");
    }
    let parts = built["messages"][0]["content"]["parts"].as_array().unwrap();
    assert_eq!(parts[0], "hello fixture");
}

#[test]
fn image_prepare_matches_fixture() {
    let built = build_image_prepare_body("sunset over ocean", "gpt-image-2");
    let golden = load_json("image_prepare_body.json");
    assert_stable_keys(&built, &golden);
    assert_eq!(built["parent_message_id"], golden["parent_message_id"]);
    assert_eq!(
        built["client_prepare_state"],
        golden["client_prepare_state"]
    );
}

#[test]
fn image_start_matches_fixture() {
    let built = build_image_start_body("a red cube on white background", "gpt-image-2");
    let golden = load_json("image_start_body.json");
    assert_stable_keys(&built, &golden);
    assert_eq!(
        built["enable_message_followups"],
        golden["enable_message_followups"]
    );
}

#[test]
fn image_start_with_refs_matches_fixture() {
    let refs = [ImageRef {
        file_id: "file-fixture-001".into(),
        mime_type: "image/png".into(),
        file_name: "input.png".into(),
        file_size: 204800,
        width: 1024,
        height: 1024,
    }];
    let built =
        build_image_start_body_with_refs("edit: make the sky sunset orange", "gpt-image-2", &refs);
    let golden = load_json("image_start_body_with_refs.json");
    assert_stable_keys(&built, &golden);
    let content_type = built["messages"][0]["content"]["content_type"]
        .as_str()
        .unwrap();
    assert_eq!(content_type, "multimodal_text");
}

#[test]
fn estuary_headers_require_bearer() {
    let golden = load_json("estuary_headers.json");
    let built = build_estuary_download_headers("REDACTED");
    assert!(validate_estuary_headers(&built).is_ok());
    assert!(golden["must_include"]
        .as_array()
        .unwrap()
        .iter()
        .any(|k| k.as_str() == Some("Authorization")));
}

#[test]
fn sse_fixture_has_skipped_mainline() {
    let raw = fs::read_to_string(fixture_path("sse_skipped_mainline.ndjson")).unwrap();
    assert!(raw.contains("skipped_mainline"));
    assert!(raw.contains("conversation.done"));
}

#[test]
fn upload_fixture_forbids_bearer_on_resource() {
    let v = load_json("upload_api_vs_resource.json");
    let must_not: Vec<_> = v["resource_put"]["must_not_include"]
        .as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_str().unwrap())
        .collect();
    assert!(must_not.contains(&"Authorization"));
    let resource_headers = serde_json::json!({"Content-Type": "image/png"});
    assert!(validate_resource_put_headers(&resource_headers).is_ok());
    let bad = serde_json::json!({"Authorization": "Bearer x"});
    assert!(validate_resource_put_headers(&bad).is_err());
}

#[test]
fn sentinel_headers_fixture_present() {
    let v = load_json("sentinel_headers.json");
    assert!(v.get("Authorization").is_some());
}
