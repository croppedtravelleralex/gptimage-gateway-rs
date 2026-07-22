# gptimage-gateway-rs

独立新项目：用 Rust 重写 ChatGPT 逆向**数据面**（编排面 → 调度 → RCA → 生产 canary）。

- **参考实现 / 生产**：`../gptimage`（Python `chatgpt2api`，Panda `:8012`）
- **本仓测试面**：Panda **`:8013`（Rust）+ `:19001`（Python protocol helper）**
- **施工总控 / 重写路线**：[plan.md](plan.md)
- **契约**：[docs/00-contract.md](docs/00-contract.md)
- **操作指导**：[docs/17-operator-guide.md](docs/17-operator-guide.md)
- **测试矩阵**：[docs/18-test-matrix.md](docs/18-test-matrix.md)
- **性能对照**：[docs/13-perf-baseline-compare.md](docs/13-perf-baseline-compare.md)

## 当前状态（2026-07-22）

| 项 | 状态 |
|----|------|
| Rust face `:8013` | ✅ 已上线（`runtime=rust`） |
| Helper `:19001` | ✅ curl_cffi / PoW / SSE |
| 文生图并发闸 | ✅ `IMAGE_GLOBAL_CONCURRENCY`（默认 3） |
| MVP 正式签字 | ⏳ 待 CF/egress 可测窗（**CF403 由号池侧解决**） |
| 生产切流 | ❌ 未做；公网仍 `:8012` |

详情与 Phase A→E 路线见 [plan.md](plan.md)。

## 路线摘要

```text
A  Rust 编排 + helper   ← 当前
B  协议补齐（edits/estuary/fixtures）
C  选号 / admission
D  RCA / llm_ops 对齐
E  R2 生产 canary（另立项）
```

## 永久非目标

- 注册机（Camoufox/OTP/邮箱池）
- FlareSolverr / 全局 clearance
- 在本仓攻坚 CF403（见 gptimage `docs/17-cf403-and-egress.md`）
- 未立项前改生产 Nginx/`8012`

## 快速命令（Panda）

```bash
cd /root/gptimage-gateway-rs && git pull --ff-only
bash scripts/panda_bringup_rust_face.sh
curl -fsS http://127.0.0.1:8013/health
PYTHONUNBUFFERED=1 python3 -u scripts/mvp_rust_conc_matrix.py http://127.0.0.1:8013
```

本地编 linux 二进制（**禁止在 panda 上 cargo**）：

```bash
cargo build --release -p gateway
cp target/release/gptimage-gateway-rs bin/
```
