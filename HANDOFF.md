# HANDOFF — gptimage-gateway-rs

最后更新：2026-07-22

## 读什么

1. [plan.md](plan.md) — **进度 + Phase A→E 重写路线**（权威）
2. [docs/00-contract.md](docs/00-contract.md) — 协议契约 / session 表 / error_class
3. [docs/18-test-matrix.md](docs/18-test-matrix.md) — 验收矩阵
4. [docs/17-operator-guide.md](docs/17-operator-guide.md) — 拓扑与故障树
5. CF/egress（号池侧）：`../gptimage/docs/17-cf403-and-egress.md`

## 当前状态

- **Phase A 已接线**：Panda `Rust :8013` + `helper :19001`；生产 `:8012` 未切流
- 仓：`https://github.com/croppedtravelleralex/gptimage-gateway-rs`；panda `/root/gptimage-gateway-rs`
- 产物：`bin/gptimage-gateway-rs`（linux amd64，本地/WSL 编译后 push）
- 生图路径：helper 默认 `make_backend` 直连；额度门禁 + 并发 Semaphore
- **阻塞 MVP 签字**：上游 CF403/egress（**不归本仓改协议硬刚**；Owner：号池/出口）

## 下一步（按优先级）

1. （外部）CF/Webshare 可测窗恢复后，跑 `mvp_rust_conc_matrix.py`，填 `docs/18` 签字栏  
2. Phase B：edits / estuary Bearer 负例 / fixtures golden  
3. Phase C：选号/admission 进编排面  
4. Phase D→E：RCA 对齐 → R2 另立项  

## 禁止

- Panda 上 `cargo build` / `docker build`
- scp 当正式发布（走 git push → pull）
- 引入 flaresolverr / 注册机
- 把 CF HTML 记成 `self` 空成功
- 未过 MVP 签字开全量调度/RCA 大改
- 未立项改生产 Nginx / `:8012`
