# HANDOFF — gptimage-gateway-rs

最后更新：2026-07-20

## 读什么

1. [plan.md](plan.md) — 施工总控（两波 + 门禁）
2. [docs/00-contract.md](docs/00-contract.md) — 协议契约 / session 表 / error_class
3. [docs/18-test-matrix.md](docs/18-test-matrix.md) — 验收矩阵
4. 对照生产：`../gptimage/docs/12-protocol-gap-vs-web.md`、`../gptimage/docs/13-performance-and-rewrite-estimate.md`

## 当前状态

- 仓：文档-only；无 Cargo 业务实现
- 生产仍在 `gptimage` / Panda `chatgpt2api-local:8012`
- Python 基线：见 `../gptimage/docs/13` 与 Panda `data/runlogs/rust-baseline-*`

## 下一步

1. STORE S1/L1（gptimage `docs/15`）硬阻塞实打上游前完成
2. 导出 `fixtures/protocol/` golden
3. MVP crates：protocol units + curl_cffi helper + 最小 HTTP
4. Panda `:8013` 隔离测生文/生图 → 矩阵出门 → 再开全量（含 RCA）

## 禁止

- Panda 上 `cargo build`
- 引入 flaresolverr / 注册机
- 未过 MVP 门禁合并全量模块
- runlogs 落 Bearer / raw token / 完整 SSE
