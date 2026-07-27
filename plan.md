# gptimage-gateway-rs 施工总控 · Rust 重写路线

最后更新：2026-07-27（P0 提交 + §6.3 六项决议闭合）  
状态：**工程基线全绿**（build / test 56 / fmt / clippy -D warnings / desense 五道门禁）；
代码**已改未提交、未部署**；Phase B 契约仍不成立。  
数据面重写：功能加权 **≈12.8%** / 工作树体量 8.3% / 已进 git 2.9% / **上游字节 0%**，见 [docs/23](docs/23-rewrite-progress.md)。  
✅ **Phase B′ 判据 1 通过** —— `wreq` 实测复现 curl_cffi 指纹，见 [docs/27](docs/27-tls-fingerprint-spike-20260726.md)。硬阻塞从「技术未知」降为「工作量」。  
⚠️ **存在两条互不知晓的 Rust 化路径**，见 §1.0′。  
⚠️ **本仓 2,707 行中只有 943 行进了 git**；且生产上跑着 598 行未入库 Rust，见 §1.0″。  
⚠️ **当前架构下性能开销下降仍 = 0%**，见 [docs/26](docs/26-perf-measured-20260726.md)。  
能力 gap 全量盘点（129 端点 / 42 数据面能力 / 71 配置键）见 [docs/24-gap-inventory.md](docs/24-gap-inventory.md)。  
**对照基准**：`../gptimage-panda`（⚠️ 漏 4 份文档）+ **panda 现采**，见 [SOURCE.md](SOURCE.md) / [docs/25](docs/25-panda-vs-rust-20260726.md)

## 0. Contract

### 目标

- 独立新项目重写 ChatGPT 逆向**数据面**，提升同机并发与稳态资源。
- 推进顺序：**协议契约可复现 → Rust 编排面 + 鉴权/UI → 调度/admission → RCA/运维对齐 → R2 生产 cutover（另立项）**。
- **当前波次**：先把**前端框架 + 简易后端**（对话/鉴权/管理）跑通；生图执行路径后置接入。

### 非目标（永久）

| 项 | 说明 |
|----|------|
| 注册机 | 不迁、不测；号源外置 |
| FlareSolverr / 全局 clearance | 不引入；生产已 `clearance.enabled=false` |
| CF403 / Webshare 出口治理 | **不在本仓攻坚**；归 `../gptimage/docs/17-cf403-and-egress.md` |
| 维护环 / Outlook OTP / Panda sync UI | 首期不做 |
| 生产 `8012` / 公网切流 | 另立项 R2 |

### 红线

- `self`（非上游）失败率必须 **= 0** 才可晋级
- estuary 下载必须主 session + Bearer
- SSE ready = payload 含 `conversation_id`（禁止 `post_ready=15s` 墙钟假 ready）
- `skipped_mainline` ≠ 换号失败
- 禁止 Panda `cargo build` / `docker build`；发布：**本地/WSL 编 linux-amd64 → git push → panda pull**
- CF HTML / `cf_edge_block` → 记 **`upstream`**，不得当 self 空成功

---

## 1. 当前进度（2026-07-26 审计后修正）

> 2026-07-26 全量审计把本节多处 ✅ 降级。原始声称与实际的逐项对照见
> [docs/23-rewrite-progress.md](docs/23-rewrite-progress.md) §4，证据见
> [docs/22-audit-2026-07-26.md](docs/22-audit-2026-07-26.md)。

### 1.0 阻断项 —— 已全部解除（2026-07-26）

| 项 | 状态 | 做法 |
|----|------|------|
| workspace 编译 | ✅ | 删掉 `SentinelTicket` 的 `Serialize`/`Deserialize` derive —— 纯内存池不需要序列化。一个动作解三件事：4 个 E0277 消失、堵住「一次 `{:?}` 泄全池 4 个明文 token」的 CRITICAL、并改手写 `Debug` 做 redact。**没有用「给 `uuid` 加 serde feature」那条路** |
| gateway 启动 | ✅ | 新增 `cors_layer_from()` 读 `GATEWAY_CORS_ORIGINS`。⚠️ 实测发现 tower-http 对 origin / methods / headers **三处**都单独 assert 与 credentials 的冲突，不只 origin —— 首版修复只改了 origin，被测试抓出来 |
| CI | ✅ | `.github/workflows/ci.yml`：fmt / clippy -D warnings / build / test / desense |
| 复用守卫语义反了 | ✅ | 原 `acquire()` 只在 `PerCallFinalize`（禁止复用）下放行，与命名互相否定。改为 `ReusePolicy::allows_pooled_acquire()`，该策略明确拒绝池化取票 |

门禁现状：

```text
cargo build --workspace        ✅
cargo test --workspace         ✅ 56 passed（原先 0 个能跑）
cargo fmt --all -- --check     ✅
cargo clippy -- -D warnings    ✅ 0 warning
check_runlog_desense.py        ✅ DESENSE_OK（清理前实测 14 处命中）
```

> ⚠️ **门禁绿 ≠ 已部署。** 这些改动尚未 commit，panda 跑的仍是 2026-07-21 的旧二进制。

### 1.0′ ⚠️ 双轨：存在两条互不知晓的 Rust 化路径

2026-07-26 发现。这是比进度百分比更要紧的结构性问题。

| | 路径 A · 树内加速器 | 路径 B · 本仓 |
|---|---|---|
| 位置 | `../gptimage/crates/` | `crates/` |
| 规模 | **1,107 行** | 2,707 行（数据面 826） |
| 形态 | `cdylib` + `rlib`，经 ctypes FFI 被 Python 调用 | 独立 axum 二进制 |
| 覆盖 | 双槽账本（account+sS）/ 调度门 / 租约池 / sediment / 调度 trace（21 事件） | HTTP face / JWT 鉴权 / 账号缓存 |
| 状态 | ✅ 编译为 `native/*.so`，**已上 panda 生产**（2026-07-25） | ✅ 编译通过、56 测试绿，但**未提交也未部署** |

本仓对路径 A **零引用**。而本仓的 `ticket_pool`（编译已修复，但仍零引用）与路径 A 已上生产的
`pre_ticket_pool.py` 语义重叠 **~80%** —— **在重造已经造好的轮子**。

**路径 A 的 crate 声明了 `rlib`，本仓可直接 `path` 依赖复用，完全绕开 FFI 层。**
可白捡的能力：`SlotLedger`（双槽 + TTL watchdog）、`DispatchGate`、`SedimentParser`、
整个 `image_schedule_trace`（阶段耗时模型 + 自动归因）。详见
[docs/24-gap-inventory.md](docs/24-gap-inventory.md) §3.2，三个处置选项见
[docs/23](docs/23-rewrite-progress.md) §4「双轨该怎么办」。

**决策前 `ticket_pool` 不应再投入**：它现在编译通过、9 个测试绿、凭据已 redact，
但仍是零引用孤儿。留着不再是技术债阻断，而是等双轨决策决定复用还是删除。

本节以下的 Phase A→E 路线图只描述路径 B —— 而实际推进最快、唯一上了生产的是路径 A。

### 1.0″ ⚠️ 供应链缺口：代码没进 git，却在生产上跑

2026-07-26 panda 现采发现。这是比双轨更直接的风险，见 [docs/25](docs/25-panda-vs-rust-20260726.md) §1.2 / §1.5。

| 侧 | 工作树 | 已进 git | 未跟踪 | panda 上有源码 |
|----|-------|---------|--------|--------------|
| 本仓（路径 B） | 2,707 | **943** | **1,764** | 是（HEAD `6509fba`，与本地 HEAD 逐字节相同） |
| `image_schedule_core`（A） | 597 | 509 | 88 | **否，只有 `.so`** |
| `image_schedule_trace`（A） | 510 | **0** | 510 | 是 |

两个方向的问题：

**① 本仓 1,764 行到不了 panda。** 未跟踪的是全部 `auth`(387)、`auth_routes`(264)、`ticket_pool`(285)、
`image_contract`(202)、`fixtures`(138)、`control_client`(107)、`error_class`(74)、`backend_routes`(36)、`state`(21)，
**外加整个 `web/`**（`git ls-files web` = 0 条）与 `fixtures/protocol/*.json` 8 份、`docs/21`–`27`。
本地相对 panda 只领先两个**纯文档** commit，且 `git rev-list --count main..develop` = **0**（两分支逐字节相同）。

> ✅ **2026-07-26 更新**：原文这里写「一旦提交，`cargo build --workspace` 又过不了（4×E0277）」——
> **这条已不成立**。P0 清完后 workspace 编译通过、56 个测试全绿。
> 现在的阻碍只剩「还没 commit」这一个动作，不再是技术问题。

运行时实测（panda 本机 curl，2026-07-26）：

| 路径 | 状态 |
|------|------|
| `/api/auth/me` | **404** |
| `/api/auth/login` | **404** |
| `/api/admin/users` | **404** |
| `/api/backend/capabilities` | **404** |
| `/v1/images/edits` | **404** |

配合 ELF `strings` 无 auth 符号，双向证实生产二进制不含这些路由。

**② 生产上跑着 598 行未入库 Rust。** `../gptimage` 的 `git status crates/` 实测：
`dispatch_gate.rs`、`lease_pool.rs`、`sediment.rs`、整个 `image_schedule_trace/` 全部 `??`。
而 `services/image_pipeline/slot_ledger.py:268-277` 的 `SlotLedgerFacade` 检测到 `native/*.so`
即切 rust 后端（`backend` 返回 `"rust"`）—— **这些未入库代码正在生产路径上执行**。
更进一步：`libimage_schedule_core.so` 已 ro 挂载进生产容器并被调用，但 **panda 上根本没有它的源码**，
无法从本机溯源到任何 commit；且 `crates/image_schedule_trace/target/` 有 debug+release+交叉三套产物，
**该 crate 曾在 panda 上编译过**（部署铁律一历史违规，已记录，本次未触碰）。

处置：本仓侧只剩「提交」这一个动作（邮箱已清、编译已过）；跨仓侧见 `HANDOFF.md` P2。

### 1.0‴ ⚠️ 性能收益当前为 0，且 `docs/13` 预估已作废

2026-07-26 panda 现采，见 [docs/26](docs/26-perf-measured-20260726.md)。

| 事实 | 数值 | 依据 |
|------|------|------|
| `docs/13` 记 Python 空闲 CPU | 0.5–0.7% | 实测 **98.5%**，偏两个数量级 |
| 98.5% 的归因 | 10 个 `image_task_service` submit worker 的 GIL 争抢 | 29 线程中 10 个各占 9.0–11.5%，全 `futex_wait_queue` |
| Rust 进程 3 天累计 CPU | **0.33 秒**（私有内存 432KB） | `/proc/<pid>/stat` |
| Rust 出站目标 | 6 个，**全指向本地 helper，零个指向 ChatGPT** | `helper_client/src/lib.rs:121-203` |
| 真实并发上限 | anyio `total_tokens`=**40** × 同账号锁串行 × GIL 单核 | 容器内实测；Rust `Semaphore(3)` 比三者都松，**不是瓶颈** |
| **系统总 RSS 变化** | **+5.2MB**（Rust 是加在 Python 前面的一层） | Python 一个进程没少 |

`docs/13` 的四行预估（RSS −50~70% / CPU −30~50% / 并发 ×2–3 / E2E +0~15%）**全部作废**，
MVP 与全量两列从提出到作废**没有任何一次实测尝试**。

完全重写（Python 归零）后的可辩护区间见 [docs/26](docs/26-perf-measured-20260726.md) §8 ——
RSS −82~93% / 稳态 CPU −85~95% / 上下文切换 −99%+ / 镜像 −96% / 并发 ×5~15 / **E2E 0%**。
**前提是把 `image_task_service.py` 2,456 行搬过来并关停 Python 容器；只重写 face 则收益恒为 0。**

### 1.1 已落地

| 项 | 状态 | 说明 |
|----|------|------|
| 仓与发布 | ✅ | GitHub `croppedtravelleralex/gptimage-gateway-rs`；`bin/` 已 `git rm --cached`（7.2MB 未 strip ELF，改走 CI artifact） |
| Rust gateway | ✅ | axum：`/health` `/api/auth/*` `/api/admin/*` `/api/backend/capabilities` `/v1/*` |
| 鉴权 | ⚠️ 代码在，未部署 | `crates/auth` SQLite + argon2 + JWT。三项 CRITICAL 已修：默认 admin 口令 → `bail!`；默认 JWT secret → `bail!`；禁用用户不生效 → `require_auth` 回查 DB（角色降级也即时生效） |
| Web UI | ⚠️ 代码在，**整个目录未跟踪** | `web/` Next 16 dashboard；`git ls-files web` = 0，且 `.gitignore` 忽略 `out/` → 静态产物按 git 链路送不到 panda |
| 对话 | ✅ | `/v1/chat/completions`（含 `stream:true` SSE 透传）；helper 侧 SSE 全文重复缺陷已修 |
| 管理 | ✅ | 概览/号池/额度/用户；新增 admin-only `GET /api/admin/status`（`/health` 移出的敏感字段）；`/ops` `/logs` 占位 |
| Helper | ✅ | `helper/protocol_bridge.py` `:19001`；全部 `/v1/internal/*` 加 `X-Helper-Token`，**未设密钥时 fail closed** |
| Phase B 契约 | ❌ 不成立 | 夹具自证，与生产漂移 17 字段。**本轮修了 1 项**（三处固定 UUID 字面量 → `new_uuid()`，原来每个请求 message id 都一样、上游当重放），剩 16 项 |
| error_class | ✅ 已修 | `client` 分支原本不可达（`fault.unwrap_or("upstream")` 使 `fault=None` 默认落 upstream）→ 改为显式 fault 优先 match。**`self=0` 红线现在可信** |
| admission 桩 | ⚠️ 孤儿 | `crates/control_client` 不被 gateway 依赖，连编译期契约都没建立 |
| Panda 拓扑 | ✅ | Rust `:8013` + helper `:19001`；生产 `:8012` **未切流** |
| Bringup | ✅ | `scripts/panda_bringup_rust_face.sh` 默认 `127.0.0.1:8013` + `AUTH_DISABLE=0` + `IMAGE_ENABLED=0`，与 §3 默认值表一致；且主动拒绝「无鉴权 + 非 loopback」组合，缺 `HELPER_INTERNAL_TOKEN`/`AUTH_JWT_SECRET` 时 fail-fast |

### 1.2 明确后置（本波不做）

| 项 | 状态 | 说明 |
|----|------|------|
| 生图运行时 | ⚠️ R1 单轮已验 | 2026-07-23 Panda `:8013` 200 @ 29.6s；但走的是 helper，Rust 侧无生图实现。矩阵签字仍待 CF 可测窗 |
| **票池骨架** | ⚠️ 仍是孤儿 | `crates/ticket_pool`：编译已通过、9 测试绿、token 已 redact、守卫语义已修正。但**仍零引用**，且与路径 A 的 `pre_ticket_pool.py` 重叠 80% —— 去留待双轨决策 |
| 图生图 edits 执行 | ⏸️ | 契约/fixtures 已有；运行时待后端接入 |
| estuary 下载执行 | ⏸️ | 头校验/fixtures 已有；运行时待后端接入 |
| MVP 生图矩阵签字 | ⏳ | 待 `IMAGE_ENABLED=1` + CF/egress 可测窗 |
| 选号/admission 进编排 | ⏳ | Phase C |
| RCA / llm_ops 对齐 | ⏳ | Phase D |
| 纯 rustls 直连上游 | ❌ | 未证明前禁止 |
| 生产 Nginx/`8012` cutover | ❌ | Phase E / R2 |

### 1.3 历史验证（Phase A 生图路径，保留记录）

| 验证 | 结果 | 备注 |
|------|------|------|
| **R1 开票+生图单轮** | ✅ 200 @ 29.6s | `qaflow` / `92.113.246.176`；b64≈1.17MB；证据 `data/runlogs/rust-ticket-verify-20260723/` |
| Rust conc=1/3 矩阵（CF 窗） | ⛔ 0 成功 | 全 `upstream`（CF403）；**self=0** |
| 同窗 A/B `:8012` | 同失败 | 非 Rust 独有 |

---

## 2. Rust 重写路线（分阶段）

```text
Phase A  Rust face + curl_cffi helper        ✅ 已接线
Phase A+ 鉴权 + Web UI + 简易后端           ⚠️ 代码在，未部署
Phase B  协议契约（fixtures/edits/estuary）  ❌ 夹具自证，判定不成立
    ↓
Phase B′ TLS 指纹等价性验证                  ✅ 判据1通过（docs/27）
    ↓
Phase C  调度面（选号/admission HTTP）
    ↓
Phase D  运维面（RCA/llm_ops 对齐）
    ↓
Phase E  R2 生产 canary / cutover（另立项）
```

### Phase B′ — TLS 指纹等价性验证（**判据 1 已通过 ✅**）

**2026-07-26 实测结论**：`wreq 6.0.0-rc` + `wreq-util 3.0.0-rc.14` **能复现 curl_cffi 的 TLS 指纹**。
完整数据见 [docs/27](docs/27-tls-fingerprint-spike-20260726.md)，spike 在 `spike/tls-fingerprint/`。

| 指纹维度 | curl_cffi 0.15.0 | wreq | 一致 |
|---------|-----------------|------|------|
| JA3N（归一化，对 cipher/扩展集合敏感） | `4c9ce260…` / `dee19b85…` | 同左 | ✅ 逐字节 |
| JA4 | `t13d1516h2_8daaf6152771_02713d6af862` | 同左 | ✅ |
| JA4_r（15 cipher + 16 扩展 + 8 签名算法全展开） | — | — | ✅ 逐项对齐 |
| Akamai（HTTP/2 SETTINGS/窗口/伪头序） | `52d84b11…` | `52d84b11…` | ✅ |
| JA3（未排序） | 不同 | 不同 | ⚠️ 见下 |

**JA3 不一致不构成失败**：真实 Chrome 自 2023 起对扩展顺序做随机化，原始 JA3 对 Chrome 本就不是稳定标识
（curl_cffi 自己三个 profile 的 JA3 也各不相同而 JA4 相同）。CF 用的是 JA3N / JA4 这类排序后指纹。
**用 JA3 判等价是错误的判据。**

⚠️ **chrome120 不稳定**：连续两轮 JA4 从 `t13d1516h2` 变为 `t13d1517h2`（扩展数 16→17）。
chrome124 / chrome131 完全稳定。迁移时应弃用 chrome120 —— 该 profile 在生产 `FP_PROFILES` 里出现 2 次。

⚠️ **必须 `http2(true)`**：设 `false` 会让 Akamai 指纹变为 `787b7899…`（不匹配）。

**性质变化**：硬阻塞从「技术未知」正式降级为「**工作量 + 实测验证**」。
[docs/26](26-perf-measured-20260726.md) §8 的完全重写收益预估（RSS −82~93% / CPU −85~95% / 并发 ×5~15）
前提成立，从「悬空」变为「待施工」。

**四条出门判据**

| # | 判据 | 状态 |
|---|------|------|
| 1 | JA3/JA4 与 curl_cffi 实测一致 | ✅ **通过** |
| 2 | 同号池账号、同出口代理下 CF 通过率不劣于 Python 基线 | ☐ 需 CF 可测窗 |
| 3 | SSE 长连接跑通一轮完整生图（prepare→start→ready→poll→estuary） | ☐ |
| 4 | `self=0` | ☐（`error_class` 的 `client` 不可达已修，该指标现在可信） |

**判据 1 通过 ≠ 能过 CF** —— CF 还看 IP 信誉、行为特征、Turnstile。判据 2 才是业务验收。

**构建成本**：BoringSSL 源码编译，首次约 10–15 分钟，需 `cmake` + `libclang`。
CI 与 panda 镜像都要预置。这是引入 `wreq` 的真实代价，不可忽略。

**若判据 2 失败**：把「数据面重写」从 §0 目标中删除，本项目定位正式改为 **face + 鉴权层**。
这是一个必须显式记录的决策点。

### Phase A+ — 鉴权 / UI / 简易后端（**后续增强**，非 Panda 对齐前置）

> Panda 对齐不要求启用本节。JWT / Web UI 在 `:8013` 现网不存在；见 [docs/28](docs/28-decisions-20260727.md) §1.4。

| 交付 | 完成判据 |
|------|----------|
| SQLite + JWT | admin/member 登录；cookie `gws_session`（**增强**，需 `AUTH_DISABLE=0`） |
| `web/` dashboard | 登录、对话、管理页；`npm run build` 绿 |
| 能力探测 | `GET /api/backend/capabilities` |
| 生图默认关 | `IMAGE_ENABLED=0`；UI 占位 |

详见 [docs/21-auth-and-ui.md](docs/21-auth-and-ui.md)。

### Phase B — 协议单位（契约层 ❌ / 运行时 ⏸️）

| 单位 | 契约 | 运行时 |
|------|------|--------|
| U-Text-SSE | ✅ | ✅ 透传 helper（helper 侧有全文重复缺陷） |
| U-Img-Prepare/Start | ❌ 漂移 17 字段 | ⏸️ |
| U-Img-Edit | ⚠️ fixtures + `ImageEditRequest` | ⏸️ `501` |
| U-Img-Estuary | ⚠️ 头校验（大小写敏感，可绕过）+ fixtures | ⏸️ |
| fixtures golden | ❌ 自证 | — |

**为什么判 ❌**：`fixtures/protocol/image_start_body.json` 与 `protocol::image_contract` 逐字段同构，连 `"fixture-user-message-id"` 占位 id 都两边一致 —— 夹具是从 Rust 输出反向生成的，不是从 Python golden 捕获的；测试只比 8 个 `STABLE_KEYS`。对照 `../gptimage/services/protocol/chatgpt_web_request.py:309-439` 已漂移 17 处（`client_contextual_info` 完全缺失、SPA 分支未实现、`custom_symbol_offsets` / `timezone_offset_min` 硬编码）。Python 源码注释明确写了这些差异**会改变上游行为**。明细见 [docs/22](docs/22-audit-2026-07-26.md) §3。

**重做判据**：夹具改为从 Python 侧真实请求捕获并附生成脚本；测试改全量 diff（白名单排除 uuid/时间戳）；双边 diff 进 CI。

**出门（B→C，生图接入后）**：运行时打通 edits/estuary；矩阵 `self=0`（需先修 `error_class` 的 `client` 不可达问题，否则该指标无效）。

### Phase C — 调度面

选号 / inflight / admission HTTP；`control_client` 桩已备，待接线。

### Phase D / E

见下文历史章节；未变。

---

## 3. 架构（当前）

```text
Browser
  → web/out（静态，可选 GATEWAY_STATIC_DIR 同域）
  → Rust gateway :8013
       · 鉴权 JWT / 角色门禁
       · 对话 / 管理 API
       · /api/backend/capabilities
       · 生图路由默认 501 deferred
  → Python protocol_bridge :19001（文本/SSE）
       · 只读挂载 ../gptimage
  → ChatGPT upstream（经 Webshare sticky）

生产 chatgpt2api-local :8012 并行存在，互不替换。
```

### 环境变量（常用）

| 变量 | 默认 | 含义 |
|------|------|------|
| `GATEWAY_LISTEN` | `0.0.0.0:8013` | Rust 面 |
| `GATEWAY_STATIC_DIR` | — | 托管 `web/out` |
| `HELPER_URL` | `http://127.0.0.1:19001` | helper |
| `PIN_ACCOUNT_FILE` | secrets/pin… | pin 账号 |
| `AUTH_JWT_SECRET` | （生产必填） | ≥32 字节 |
| `AUTH_BOOTSTRAP_ADMIN_*` | — | 首次 bootstrap admin |
| `IMAGE_ENABLED` | **`0`** | `1` 开启生图（后端接入后） |
| `IMAGE_GLOBAL_CONCURRENCY` | `3` | 生图闸（仅 IMAGE_ENABLED=1） |
| `AUTH_DISABLE` | `0` | dev 跳过鉴权；为真时**同时跳过 JWT 密钥长度校验**并给匿名请求注入 admin 角色 |

⚠️ 上表是**代码默认值**。`scripts/panda_bringup_rust_face.sh` 覆盖了其中三项（`AUTH_DISABLE=1`、`IMAGE_ENABLED=1`、不注入 `AUTH_JWT_SECRET` / `AUTH_BOOTSTRAP_ADMIN_*` / `GATEWAY_STATIC_DIR`），叠加 `GATEWAY_LISTEN=0.0.0.0` 后 Panda `:8013` 实际是**公网监听 + 无鉴权**状态。

完整鉴权变量见 [docs/21-auth-and-ui.md](docs/21-auth-and-ui.md)（该表缺至少 8 个实际读取的变量，见 [docs/22](docs/22-audit-2026-07-26.md) §7）。

---

## 4. 仓布局

```text
gptimage-gateway-rs/
  plan.md
  HANDOFF.md
  bin/gptimage-gateway-rs   ← 7.2MB ELF，建议移出 git 改 CI artifact
  crates/{gateway,auth,protocol,helper_client}
  crates/{ticket_pool,control_client}   ← frozen，不进 workspace
  web/                    ← Next 16 UI
  helper/protocol_bridge.py
  fixtures/protocol/      ← Phase B golden（全量）
  scripts/panda_bringup_rust_face.sh
  docs/{00,13,17,18,21}-*.md
  data/{auth.db,runlogs/}
```

---

## 5. 本地开发

```bash
# Rust
cargo test
cargo build --release -p gateway

# Web
cd web && npm run build    # → web/out
cd web && NEXT_PUBLIC_API_BASE=http://127.0.0.1:8013 npm run dev

# 启动（示例）
AUTH_JWT_SECRET="dev-only-change-me-in-production-32b" \
AUTH_BOOTSTRAP_ADMIN_USER=admin \
AUTH_BOOTSTRAP_ADMIN_PASSWORD=changeme \
GATEWAY_STATIC_DIR=web/out \
PIN_ACCOUNT_FILE=secrets/pin_account.json \
./target/release/gptimage-gateway-rs
```

Panda：禁止 `cargo build`；`git pull` + 预编译 `bin/` + `bash scripts/panda_bringup_rust_face.sh`。

---

## 6. 晋级检查表（2026-07-26 修正）

### 6.0 建议执行顺序

**第 1 步 —— 冻结 `ticket_pool`（一个动作，两个收益）**

摘掉 `ticket_pool` 的 workspace member 条目，同时解决两件事：

| 收益 | 说明 |
|------|------|
| P0 编译阻断消失 | 4 个 E0277 全在这个 crate；摘掉后 5 crate 全绿、19 个测试可跑 |
| 停止重复造轮子 | 它与路径 A 已上生产的 `pre_ticket_pool.py` 重叠 ~80%（§1.0′） |

比「给 `uuid` 加 `serde` feature」更可取 —— 加 feature 只是让一个零引用、语义自相矛盾
（`acquire()` 仅在"不复用"策略下放行）的孤儿 crate 编译通过，等于把技术债固化进构建图。

**第 2 步 —— 双轨决策**（合流 / 各行其道 / 收编，见 [docs/23](docs/23-rewrite-progress.md) §4）

必须先定，否则 Phase C 无从设计：选号/admission 到底是复用路径 A 的 `SlotLedger`+`DispatchGate`，
还是在本仓重写一遍。倾向**合流** —— 对方已声明 `rlib`，`path` 依赖即可，无需碰 FFI。

**第 3 步 —— 其余 P0**

### 6.1 P0 清单 —— 已全部完成 ✅

- [x] `ticket_pool` 编译阻断 → 删 serde derive（非加 feature），一并修复明文 token 泄露与反了的守卫语义
- [x] CORS → `cors_layer_from()` 读 env allowlist；实测发现 methods/headers 也与 credentials 冲突
- [x] bringup 默认值反转 → loopback + `AUTH_DISABLE=0` + `IMAGE_ENABLED=0`，并主动拒绝危险组合
- [x] 建 CI → `.github/workflows/ci.yml` 五道门禁；desense 脚本扫描路径已修（清理前实测报 14 处命中）
- [x] 清凭据 → 删 19 个死脚本（含 7 个带真实邮箱）、`bin/` 出 git、`.gitignore` 补 5 类
- [ ] ~~**提交这 1,764 行**~~ —— ✅ 2026-07-27

### 6.2 Phase

- [x] L0：契约 + 仓骨架
- [x] Phase A：Rust face + helper + Panda `:8013`
- [ ] Phase A+：鉴权 + Web UI + 简易后端 —— 代码在，**未部署**且有 3 项安全 CRITICAL
- [ ] Phase B（契约）：**需重做** —— 夹具从 Python 侧真实捕获 + 全量 diff
- [ ] Phase B（运行时）：生图/edits/estuary 执行
- [ ] Phase A 出门：生图矩阵签字（CF 可测窗 + `self=0`；需先修 `error_class` 偏置）
- [x] Phase B′ 判据 1：TLS 指纹等价性 —— `wreq` 实测通过（[docs/27](docs/27-tls-fingerprint-spike-20260726.md)）
- [ ] Phase B′ 判据 2/3/4：CF 通过率 / SSE 全程 / `self=0`
- [ ] Phase C：选号 / admission 接线
- [ ] Phase D：RCA / 指标对齐
- [ ] Phase E / R2：生产立项

真 ✅ **2 / 10**（原 9 项检查表下为 2/9，文档此前声称 4/9）。
数据面重写：功能加权 **≈12.8%** / 工作树体量 8.3% / **已进 git 2.9%** / 已部署 5.4% / 上游字节 **0%**，
见 [docs/23-rewrite-progress.md](docs/23-rewrite-progress.md) §1。

### 6.3 架构决策 —— ✅ 已闭合（2026-07-27，以 Panda 现网为准）

详见 [docs/28-decisions-20260727.md](docs/28-decisions-20260727.md)。

| # | 决策项 | 决议 | 落地 |
|---|--------|------|------|
| 1 | 双轨处置 | **合流** — `path` 依赖 `image_schedule_core` + `image_schedule_trace` | Phase C 接线；路径 A 未入库源码先推 `gptimage` git |
| 2 | `ticket_pool` | **冻结** — 移出 workspace，保留源码 | `Cargo.toml` 已摘除 |
| 3 | `control_client` | **移除** — 移出 workspace | Phase C 对接 Python 调度面，不用 phantom admission |
| 4 | 鉴权模型 | **先对齐 Panda**（`:8013` 无鉴权、R2 前 `:8012` API key）；JWT/Web UI = **后续增强** | API key = P1；`auth`/`web` 不阻塞 Panda 部署 |
| 5 | 异步图片队列 | **在范围内**（数据面） | 分母已含 `image_task_service` 2,456 行 |
| 6 | CPA 7 端点 | **非永久非目标** | gap 待对齐，优先级 Phase D |

## 7. 关联

- **生产实测对照**：[docs/25-panda-vs-rust-20260726.md](docs/25-panda-vs-rust-20260726.md)
- **性能实测与预估**：[docs/26-perf-measured-20260726.md](docs/26-perf-measured-20260726.md)
- **审计报告**：[docs/22-audit-2026-07-26.md](docs/22-audit-2026-07-26.md)
- **进度量化**：[docs/23-rewrite-progress.md](docs/23-rewrite-progress.md)
- **能力 gap**：[docs/24-gap-inventory.md](docs/24-gap-inventory.md)
- 鉴权/UI：[docs/21-auth-and-ui.md](docs/21-auth-and-ui.md)（描述未部署版本）
- CF/egress：`../gptimage/docs/17-cf403-and-egress.md`
- 指针：`../gptimage/docs/14-rust-rewrite-plan.md`
- 矩阵：`docs/18-test-matrix.md`

> 文档冲突时优先级：**25 / 26（panda 现采）> 22 / 23 / 24（本地分析）> 其余**。
