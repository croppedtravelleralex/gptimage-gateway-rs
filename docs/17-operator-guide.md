# 17 — 操作指导

最后更新：2026-07-22

## 读哪份

| 意图 | 文档 |
|------|------|
| 进度与 Phase A→E 路线 | `../plan.md` |
| 协议红线 | `00-contract.md` |
| 是否出门 | `18-test-matrix.md` |
| 性能数字 | `13-perf-baseline-compare.md` + `../gptimage/docs/13-*.md` |
| CF403 / 出口 | `../gptimage/docs/17-cf403-and-egress.md`（**号池侧**） |

## Panda 拓扑（实测）

| 服务 | 端口 | 角色 |
|------|------|------|
| `chatgpt2api-local` | **8012** | 生产 Python（公网） |
| `gptimage-gateway-rs`（Rust） | **8013** | MVP 测试 face；`runtime=rust` |
| `protocol_bridge`（Python helper） | **19001**（loopback） | curl_cffi / PoW / SSE；只被 Rust 调用 |

- 公网 `https://gptimage.relai.asia` **保持**反代 8012，直至 R2 立项。
- Bringup：`scripts/panda_bringup_rust_face.sh`（先停旧 Python face 容器）。
- 回滚：停 Rust + `docker rm -f gptimage-gateway-rs-helper`；可选 `panda_bringup_mvp_face.sh`。
- 禁止本仓 compose 引入 flaresolverr；禁止 panda 上 cargo/docker build。

## 观察号 / 测试号纪律

- `verified_ready` ∧ 可调度 ∧ 唯一 proxy binding
- 不用 `identity_isolated` 同伴做热路径压测
- 并发：异号 + 异 `proxy_host`；同 pin 并发易放大 CF（记 upstream）
- 先读 health：`image_generation_paused`、inflight、admission 余席（生产侧）
- 生图模型用现网支持列表（如 `gpt-image-2`）；注意 duplicate-prompt 窗
- 矩阵：`PYTHONUNBUFFERED=1 python3 -u scripts/mvp_rust_conc_matrix.py http://127.0.0.1:8013`

## 开/关流量

- 测试环：起停 `:8013` + helper 即可
- 生产 canary：仅 R2；默认不切公网
- 回滚：停 Rust face；保留 Python `:8012` 热路径

## 故障树（self vs upstream）

| 现象 | 先查 |
|------|------|
| CF HTML / chat_requirements / conversation 403 | **`upstream`**；代理与 egress（号池侧） |
| `no available image quota`（helper sticky） | 查是否误开 `MVP_FORCE_POOL_STICKY`；默认应 `make_backend` 直连 |
| estuary 403 access denied | `self`：是否丢 Bearer / 误用 resource session |
| 空 data / image.task 200 | `self`：假成功，硬不合格 |
| skipped_mainline 后换号 | `self`：语义回归 |
| 429 duplicate prompt | `gate`：改 prompt 或等窗 |
| 429 image_service_busy / image_quota_insufficient | `gate` / `quota` |
| inflight 不回零 | `self`：迟到 acquire / 双释放 |
| SSE 僵死数十分钟 | `self`：缺 post_ready/wall/cancel；查 Phase A 安全阀 |

## 脱敏

runlogs 允许：token_hash、error_class、latency、status、b64 **长度**。  
禁止：access_token、Authorization、proxy 密码、完整 SSE。  
验收：`rg -n "Bearer |eyJ" data/runlogs` 应无业务命中。

## 本阶段不要做

- 写注册机 / FlareSolverr
- 在本仓攻坚 CF403（交给号池/egress）
- 未过 MVP 矩阵开全量 RCA 实现
- 改生产 Nginx 切流
- Panda 上编译 Rust
