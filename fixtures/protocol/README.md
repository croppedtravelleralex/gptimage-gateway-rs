# fixtures/protocol

与 Python golden 可差分的 JSON/文本夹具（Phase B 已齐）。

| 文件 | 状态 | 内容 |
|------|------|------|
| `chat_body.json` | ✅ | `build_text_conversation_body` |
| `image_prepare_body.json` | ✅ | prepare |
| `image_start_body.json` | ✅ | start（无 refs） |
| `image_start_body_with_refs.json` | ✅ | multimodal + attachments（edits） |
| `sentinel_headers.json` | ✅ | sentinel 头集合 |
| `sse_skipped_mainline.ndjson` | ✅ | 含 skipped_mainline 片段 |
| `estuary_headers.json` | ✅ | 必须含 Authorization |
| `upload_api_vs_resource.json` | ✅ | API JSON vs resource PUT 无 Bearer |

Rust 差分：`cargo test -p protocol --test fixtures`  
**禁止**夹具含真实 token。
