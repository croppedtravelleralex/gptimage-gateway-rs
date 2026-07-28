# gptimage-gateway-rs

独立新项目：Rust **编排面 + 鉴权/UI**；协议数据面逐步重写。对照生产见 [SOURCE.md](SOURCE.md)。

## 非 Rust 版本来源

| | |
|--|--|
| 本地 | `D:\SelfMadeTool\AutoRegister\gptimage` |
| 相对路径 | [`../gptimage`](../gptimage) |
| Panda | `/root/gptimage` · 生产 **`:8012`** |

## 文档索引

| 文档 | 用途 |
|------|------|
| [plan.md](plan.md) | 进度 + Phase A→E 路线（权威） |
| [HANDOFF.md](HANDOFF.md) | 接手入口 |
| [docs/21-auth-and-ui.md](docs/21-auth-and-ui.md) | 鉴权 + Web UI |
| [docs/00-contract.md](docs/00-contract.md) | 协议契约 |
| [docs/17-operator-guide.md](docs/17-operator-guide.md) | 运维 / bringup |
| [docs/18-test-matrix.md](docs/18-test-matrix.md) | 验收矩阵 |

最后更新：2026-07-28

## 当前状态（2026-07-28）

| 项 | 状态 |
|----|------|
| **总进度（本地可验收）** | **≈ 99%** — 见 [docs/23](docs/23-rewrite-progress.md) |
| Rust gateway `:8013` | ✅ 本地 WSL 全栈（JWT + upstream 数据面） |
| **`crates/upstream/` 数据面** | ✅ chat/image/stream + estuary |
| Web UI `web/` | ✅ dashboard + `/chat` `/image` |
| Helper `:19001` | ✅ 可选降级（`UPSTREAM_ONLY=1` 默认跳过） |
| Phase B fixtures | ✅ 全量 golden 差分 |
| 生图运行时（gateway 接线） | ✅ `DATA_PLANE=upstream` |
| GHCR + upstream-probe | ✅ publish workflow |
| Panda `:8013` MVP | **已退役**（2026-07-28）；`panda_bringup_rust_face.sh` 已禁用 |
| 生产 `:8012` | **不动**（100% = R2 切流，另立项） |

## 路线摘要

```text
A    Rust 编排 + helper              ✅
A+   鉴权 + Web UI + 简易后端        ✅
B    协议契约（fixtures/edits/estuary） ✅ 契约层
     生图/edits/estuary 运行时        ✅ upstream 接线
C    选号 / admission                ⏸️ 可选后置
D    RCA / llm_ops
E    R2 生产 canary（另立项）        ⏸️ 100% 门槛
```

## 快速命令

```bash
# 测试
cargo test
cd web && npm run build

# 本地开发（主路径）
bash scripts/local_bringup_wsl.sh          # gateway + UI（默认 upstream，无 helper）
bash scripts/local_smoke_upstream.sh       # chat + capabilities
STREAM_ENABLED=1 bash scripts/local_smoke_upstream.sh  # + stream chat leg
cargo run -p upstream-probe --release      # 需 secrets/pin_account.json（Panda 导号）
```

Panda `:8013` MVP **已停服**；`scripts/panda_bringup_rust_face.sh` 已禁用。完整后**独立上线**，不替换现网 `:8012`。

本地编 linux 二进制：

```bash
cargo build --release -p gateway && cp target/release/gptimage-gateway-rs bin/
```

## 永久非目标

注册机 · FlareSolverr · 本仓攻坚 CF403 · 未立项改生产 `:8012`
