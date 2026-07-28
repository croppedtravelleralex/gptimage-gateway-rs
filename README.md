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

## 当前状态（2026-07-23 表需对照 HANDOFF 更新）

| 项 | 状态 |
|----|------|
| Rust face `:8013` | ✅ 鉴权 + 对话 + 管理 API（panda 仍跑旧 MVP） |
| **`crates/upstream/` 数据面** | ✅ **Panda 生图探针签字** |
| Web UI `web/` | ✅ dashboard |
| Helper `:19001` | ✅ 文本/SSE 桥接（gateway 出站仍依赖） |
| Phase B fixtures | ✅ 全量 golden 差分 |
| 生图运行时（gateway 接线） | ⏳ upstream 已通，face 未切 |
| GHCR + upstream-probe | ✅ publish workflow；Panda pull 待授权 |
| 生产切流 | ❌ 公网仍 `:8012` |

## 路线摘要

```text
A    Rust 编排 + helper              ✅
A+   鉴权 + Web UI + 简易后端        ✅
B    协议契约（fixtures/edits/estuary） ✅ 契约层
     生图/edits/estuary 运行时        ⏸️ 后置
C    选号 / admission
D    RCA / llm_ops
E    R2 生产 canary（另立项）
```

## 快速命令

```bash
# 测试
cargo test
cd web && npm run build

# Panda（禁止 cargo build）
cd /root/gptimage-gateway-rs && git pull --ff-only
bash scripts/panda_bringup_rust_face.sh
curl -fsS http://127.0.0.1:8013/api/backend/capabilities
```

本地编 linux 二进制：

```bash
cargo build --release -p gateway && cp target/release/gptimage-gateway-rs bin/
```

## 永久非目标

注册机 · FlareSolverr · 本仓攻坚 CF403 · 未立项改生产 `:8012`
