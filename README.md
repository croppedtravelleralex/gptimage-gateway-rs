# gptimage-gateway-rs

独立新项目：用 Rust 重写 ChatGPT 逆向**数据面**（最小生文/生图 → 全量含 RCA 运维指标对齐）。

- **参考实现 / 生产**：`../gptimage`（Python `chatgpt2api`，Panda `:8012`）
- **本仓**：开发与测试；**禁止**注册机与 FlareSolverr
- **施工总控**：[plan.md](plan.md)
- **契约**：[docs/00-contract.md](docs/00-contract.md)
- **操作指导**：[docs/17-operator-guide.md](docs/17-operator-guide.md)
- **测试矩阵**：[docs/18-test-matrix.md](docs/18-test-matrix.md)
- **性能对照**：[docs/13-perf-baseline-compare.md](docs/13-perf-baseline-compare.md)

## 两波路线

1. **MVP**：最小文本 + 生图协议单位 → Panda **隔离端口**（例 `:8013`）测通（`self=0`）
2. **全量**：选号/admission + RCA/运维指标对齐（测通前禁止开工）

## 永久非目标

- 注册机（Camoufox/OTP/邮箱池）
- FlareSolverr / 全局 clearance 清障栈
- 生产 Nginx/`8012` 切流（另立项 R2）

## 状态

文档骨架已就绪；Rust 业务 crate **未开工**。
