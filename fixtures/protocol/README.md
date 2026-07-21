# fixtures/protocol

放置与 Python golden 可差分的 JSON/文本夹具。

## 约定文件（落地时补齐）

| 文件 | 内容 |
|------|------|
| `chat_body.json` | `build_chat_body` 稳定字段 |
| `image_prepare_body.json` | prepare |
| `image_start_body.json` | start（可无 refs） |
| `image_start_body_with_refs.json` | multimodal + attachments |
| `sentinel_headers.json` | sentinel 头集合 |
| `sse_skipped_mainline.ndjson` | 含 skipped_mainline 片段 |
| `estuary_headers.json` | 必须含 Authorization |
| `upload_api_vs_resource.json` | API JSON vs resource PUT 无 Bearer |

导出：由 `gptimage` 测试或脚本 dump；本仓 CI 与 Rust 解析差分。  
**禁止**夹具含真实 token。
