# 17 — 操作指导

最后更新：2026-07-20

## 读哪份

| 意图 | 文档 |
|------|------|
| 怎么推进两波 | `../plan.md` |
| 协议红线 | `00-contract.md` |
| 是否出门 | `18-test-matrix.md` |
| 性能数字 | `13-perf-baseline-compare.md` + `../gptimage/docs/13-*.md` |

## Panda 拓扑

| 服务 | 端口 | 角色 |
|------|------|------|
| `chatgpt2api-local` | **8012** | 生产 Python（公网） |
| `gptimage-gateway-rs`（未来） | **8013**（建议） | MVP/全量**测试**；不占公网 |

- 公网 `https://gptimage.relai.asia` **保持**反代 8012，直至 R2 立项。
- 禁止本仓 compose 引入 flaresolverr。

## 观察号 / 测试号纪律

- `verified_ready` ∧ 可调度 ∧ 唯一 proxy binding
- 不用 `identity_isolated` 同伴做热路径压测
- 并发：`image_account_concurrency=1`；串行优先
- 先读 health：`image_generation_paused`、inflight、admission 余席
- 生图模型用现网支持列表（如 `gpt-image-2`）；注意 duplicate-prompt 窗

## 开/关流量（未来）

- 测试环：起停 `:8013` 容器即可
- 生产 canary：仅 R2；默认 `rust_gateway.*=false`
- 回滚：关开关 / 停 sidecar；保留 Python 热路径 ≥28 天

## 故障树（self vs upstream）

| 现象 | 先查 |
|------|------|
| CF HTML / chat_requirements 403 | `upstream`；代理与 egress |
| estuary 403 access denied | `self`：是否丢 Bearer / 误用 resource session |
| 空 data / image.task 200 | `self`：假成功，硬不合格 |
| skipped_mainline 后换号 | `self`：语义回归 |
| 429 duplicate prompt | `gate`：改 prompt 或等窗 |
| 429 image_service_busy | `gate`：admission，勿绕过 |
| inflight 不回零 | `self`：迟到 acquire / 双释放 |

## 脱敏

runlogs 允许：token_hash、error_class、latency、status、b64 **长度**。  
禁止：access_token、Authorization、proxy 密码、完整 SSE。  
验收：`rg -n "Bearer |eyJ" data/runlogs` 应无业务命中。

## 本阶段不要做

- 写注册机 / FlareSolverr
- 未过 MVP 矩阵开全量 RCA 实现
- 改生产 Nginx 切流
- Panda 上编译 Rust
