# 13 — 性能基线对照（相对 gptimage 生产）

最后更新：2026-07-20  
权威数字：`../gptimage/docs/13-performance-and-rewrite-estimate.md`  
成功 runlog（Panda）：`rust-baseline-retry-20260720-173225.json`

## Python `:8012` 基线（复用现网账号/代理）

| 维 | 值 |
|----|-----|
| 空闲 CPU / Mem | ~0.5–0.7% / ~160–230 MiB |
| schedulable / clearance | 6 / false |
| 文本 | **3/4 ok**；成功 ~5.5–13.4s；1× CF upstream；**self=0** |
| 生图 `gpt-image-2` | **3/4 ok**；成功 ~43–54s；b64≈1.0–1.1M；1× sync wait timeout；**self=0** |

## Rust 预估 / 实测空列

| 维 | 保守（helper） | 理想 | MVP `:8013` | 全量 |
|----|----------------|------|-------------|------|
| RSS | −20%~−40% | −50%~−70% | | |
| CPU 高负载 | −10%~−25% | −30%~−50% | | |
| 同机并发 | ×1.3–2.0 | ×2–3 | | |
| 生图 E2E | +0%~+15% | +0%~+10% | | |
| self 失败 | — | — | **必须 0** | **必须 0** |

原则：**self=0 优先于变快**。
