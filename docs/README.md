# docs — gptimage-gateway-rs

| 文件 | 用途 |
|------|------|
| [00-contract.md](00-contract.md) | 协议契约、error_class、fixtures、鉴权、Phase B |
| [13-perf-baseline-compare.md](13-perf-baseline-compare.md) | ⛔ **预估已作废** — 保留记录，真数字见 26 |
| [17-operator-guide.md](17-operator-guide.md) | Panda 拓扑、bringup、故障树（2026-07-26 按实测改写） |
| [18-test-matrix.md](18-test-matrix.md) | 验收矩阵与签字栏 |
| [21-auth-and-ui.md](21-auth-and-ui.md) | 鉴权、Web UI、环境变量（**描述的是未部署版本**） |
| [22-audit-2026-07-26.md](22-audit-2026-07-26.md) | **全量审计** — 构建阻断、7 安全 CRITICAL、契约自证、文档不符 |
| [23-rewrite-progress.md](23-rewrite-progress.md) | **重写进度量化** — 六个口径、双轨结构、Phase 声称/实际对照 |
| [24-gap-inventory.md](24-gap-inventory.md) | **能力 gap 全量盘点** — 129 端点 / 42 数据面能力 / 20 种 SSE 事件 / 13 条重试策略 / 71 配置键 |
| [25-panda-vs-rust-20260726.md](25-panda-vs-rust-20260726.md) | **生产实测对照** — 代码/文档/运行时三维差异；1,764 行未提交；文档≠运行系统 |
| [26-perf-measured-20260726.md](26-perf-measured-20260726.md) | **性能实测与预估** — 98.5% CPU 归因、架构约束、当前收益 0%、完全重写后分维度预估 |
| [27-tls-fingerprint-spike-20260726.md](27-tls-fingerprint-spike-20260726.md) | **TLS 指纹实测** — Phase B′ 判据 1 通过；`wreq` 复现 curl_cffi 指纹，chrome120 应弃用 |
| [28-decisions-20260727.md](28-decisions-20260727.md) | **架构决策** — §6.3 六项闭合（以 Panda 现网为准） |

权威进度：[../plan.md](../plan.md) · 接手：[../HANDOFF.md](../HANDOFF.md) · 对照基准：[../SOURCE.md](../SOURCE.md)

## 阅读顺序

新接手按 `HANDOFF` → `25`（现状实证）→ `22`（问题清单）→ `23`（进度）→ `plan` 读。

## 文档可信度

> 2026-07-26 审计后，`00` / `13` / `17` / `18` / `21` 五份均有与代码不符之处，逐项对照见 [22](22-audit-2026-07-26.md) §7。
> 其中 `13` 与 `17` 已于 2026-07-26 晚按 panda 实测改写；`21` 尚未改，
> 它描述的鉴权/UI 在生产二进制里根本不存在（`/me` 实测 404）。

**冲突时的优先级**：`25` / `26`（生产现采）> `22` / `23` / `24`（本地分析）> 其余。
