# crates/

| crate | 职责 | workspace |
|-------|------|-----------|
| `gateway` | axum HTTP：鉴权、对话、管理 API、能力探测；生图默认 deferred | ✅ |
| `auth` | SQLite + argon2 + JWT；bootstrap admin | ✅ |
| `protocol` | OpenAI 形状、`error_class`、`image_contract`（Phase B） | ✅ |
| `helper_client` | 调 `:19001` protocol_bridge（文本/SSE/额度/号池） | ✅ |
| `ticket_pool` | ~~票池骨架~~ | ❌ frozen — 见 [docs/28](../docs/28-decisions-20260727.md) |
| `control_client` | ~~admission HTTP 桩~~ | ❌ removed — 见 [docs/28](../docs/28-decisions-20260727.md) |

```bash
cargo test
cargo build --release -p gateway
```
