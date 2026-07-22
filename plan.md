# gptimage-gateway-rs 施工总控 · Rust 重写路线

最后更新：2026-07-22  
状态：**Phase A（Rust face + helper）已上线 Panda `:8013`**；生图 KPI 卡在 **上游 CF403/egress**（由号池/出口侧解决，非本仓协议 self）。正式 MVP 矩阵签字仍待 CF 窗可测时补齐。  
对照生产：`../gptimage`（Panda `chatgpt2api-local:8012`）

## 0. Contract

### 目标

- 独立新项目重写 ChatGPT 逆向**数据面**，提升同机并发与稳态资源；**端到端生图不以变快为 KPI**（健康窗目标约 40–60s/张，墙钟随并发并行）。
- 推进顺序：**协议单位可复现 → Rust 编排面 → 调度/admission → RCA/运维对齐 → R2 生产 cutover（另立项）**。

### 非目标（永久）

| 项 | 说明 |
|----|------|
| 注册机 | 不迁、不测；号源外置 |
| FlareSolverr / 全局 clearance | 不引入；生产已 `clearance.enabled=false` |
| CF403 / Webshare 出口治理 | **不在本仓攻坚**；归 `../gptimage/docs/17-cf403-and-egress.md` 与号池运维 |
| 维护环 / Outlook OTP / Panda sync UI | 首期不做 |
| 生产 `8012` / 公网切流 | 另立项 R2 |

### 红线

- `self`（非上游）失败率必须 **= 0** 才可晋级
- estuary 下载必须主 session + Bearer
- SSE ready = payload 含 `conversation_id`（禁止 `post_ready=15s`）；优先 `file_id`/`complete_predicate` 早退
- `skipped_mainline` ≠ 换号失败
- 禁止 Panda `cargo build` / `docker build`；正式发布：**本地/CI 编 linux-amd64 → git push → panda `git pull`**
- 满载语义：429，禁止空 `data` / `object=image.task` 假成功
- CF HTML / `cf_edge_block` → 记 **`upstream`**，不得当 self 空成功

---

## 1. 当前进度（2026-07-22）

### 1.1 已落地（可运行）

| 项 | 状态 | 说明 |
|----|------|------|
| 仓与发布 | ✅ | GitHub `croppedtravelleralex/gptimage-gateway-rs`（private）；产物 `bin/gptimage-gateway-rs`（linux amd64） |
| Rust gateway | ✅ | `crates/gateway` axum：`/health` `/v1/models` `/v1/chat/completions` `/v1/images/generations` `/v1/quota[/refresh]` `/v1/accounts/candidates` |
| 并发闸 | ✅ | 进程内 `IMAGE_GLOBAL_CONCURRENCY`（默认 3）`Semaphore` |
| 多号 | ✅ | `X-Preferred-Account-Email`；启动时种子 helper candidates（unique `proxy_host`） |
| Helper | ✅ | `helper/protocol_bridge.py`：`HELPER_LISTEN=127.0.0.1:19001`；curl_cffi / PoW / SSE |
| 生图身份 | ✅ | 默认 `make_backend` 直连（池完整 fp/proxy）；`MVP_FORCE_POOL_STICKY=1` 才走号池 sticky |
| 额度门禁 | ✅ | 生图前 live `/v1/quota/refresh`；不足 → `429 fault=quota` |
| SSE 安全阀 | ✅ | soft `post_ready≈50` + `complete_predicate` + wall≈70s（防僵尸 SSE） |
| Panda 拓扑 | ✅ | **Rust `:8013` + helper `:19001`**；生产 `:8012` **未切流** |
| Bringup | ✅ | `scripts/panda_bringup_rust_face.sh`；矩阵 `scripts/mvp_rust_conc_matrix.py` |

健康样例（期望）：

```json
{"ok":true,"runtime":"rust","helper_ok":true,"image_global_concurrency":3,"proto_bridge":true,"wave":"mvp"}
```

### 1.2 已验证（证据摘要）

| 验证 | 结果 | 备注 |
|------|------|------|
| 早期 Python face 串行生图 | ✅ ~45–51s / `self=0` | 池身份 + post_ready/complete_predicate；额度消耗可复核 |
| Rust face 接线 | ✅ | `runtime=rust`；quota/candidates/image 进 helper |
| Rust conc=1/3 矩阵（CF 窗） | ⛔ 0 成功 | 全 `upstream`（CF403 / wall / curl timeout）；**self=0** |
| 同窗 A/B `:8012` | 同失败/挂起 | 证实非 Rust 独有 |

### 1.3 明确未做 / 阻塞

| 项 | 状态 | Owner |
|----|------|-------|
| CF403 / Webshare 出口可用窗 | 进行中 | **号池/egress（用户侧）**；见 gptimage `docs/17` |
| MVP 正式签字（生文≥5 + 生图≥5，健康窗） | ⏳ 待 CF 可测 | 本仓矩阵补跑 |
| 图生图 edits / estuary 负例夹具 | ⏳ | Phase B |
| 选号/admission 进 Rust | ⏳ | Phase C |
| RCA / llm_ops / risk 对齐 | ⏳ | Phase D |
| 纯 rustls 直连上游（去 helper） | ❌ 未证明前禁止 | 远期 |
| 生产 Nginx/`8012` cutover | ❌ | Phase E / R2 另立项 |

---

## 2. Rust 重写路线（分阶段）

```text
Phase A  Rust face + curl_cffi helper     ← 当前
    ↓  CF egress 可用 + MVP 矩阵签字
Phase B  协议单位补齐（edits/estuary/fixtures）
    ↓
Phase C  调度面（选号/inflight/admission HTTP）
    ↓
Phase D  运维面（RCA/llm_ops/error_class 对齐）
    ↓
Phase E  R2 生产 canary / cutover（另立项）
```

### Phase A — 编排面 MVP（当前）

**目标**：OpenAI 兼容 HTTP 由 Rust 编排；出站 TLS/PoW/SSE 仍走 Python helper。

| 交付 | 完成判据 |
|------|----------|
| `:8013` Rust + `:19001` helper | health `runtime=rust` ∧ `helper_ok` |
| 文本 + 文生图 + quota | 固定/preferred 账号可打通 |
| 全局生图并发闸 | conc=1 与 conc=3 同健康窗单张延迟量级 |
| 发布路径 | WSL/本地 `cargo build --release` → `bin/` → push → panda pull |

**出门（A→B）**：

1. Owner 解决 CF/egress，出现稳定可测窗  
2. `mvp_rust_conc_matrix.py`（或 18 矩阵）：生图成功样张；**`self=0`**  
3. 健康窗：单张约 **40–60s**（允许 upstream 剔除后统计）  
4. 脱敏 runlogs 落盘；18 签字栏填写

### Phase B — 协议单位补齐

| 单位 | 对照 Python | 要点 |
|------|-------------|------|
| U-Text-SSE | `stream_conversation` | 可选流式（A 可先非流式） |
| U-Img-Edit | `_upload_image` + edit | 与 generations 同级 |
| U-Img-Estuary | `download_image_bytes` | Bearer；负例必须失败 |
| fixtures | `fixtures/protocol/` | golden 差分；`PROTOCOL_CONTRACT_VERSION` |

**出门（B→C）**：M-I4/M-I5/M-I6 与夹具绿；仍 `self=0`。

### Phase C — 调度面

| 模块 | 要求 |
|------|------|
| 选号 | Rust 调控制面 HTTP（或 helper 内薄封装）；禁止静默换号破坏 sticky |
| inflight / 释槽 | 迟到 acquire / 双释放回归；泄漏=0 |
| admission | 满载 429 `image_service_busy`；pause 对齐 |
| SCHED breakdown | 空池可归因（对账 Python） |

**出门（C→D）**：F-S1…F-S5 / F-B1 签字。

### Phase D — 运维 / RCA 对齐

| 模块 | 要求 |
|------|------|
| `error_class` | 与 `00-contract` / llm_ops 可对账 |
| RCA / `/ops` | 优先 UI 留 Python；指标源对齐 Rust |
| risk / nurture | 读计数；禁假聊；巡检默认可 OFF |

**出门（D→E）**：全量矩阵 F-R* 签字 + 观察窗。

### Phase E — R2 生产（另立项）

- 公网仍反代 `:8012`，直至书面立项  
- canary 比例、回滚（停 Rust / 切回 Python）≥28 天热路径保留  
- **禁止**本仓私自改 Nginx

---

## 3. 架构（Phase A）

```text
Client
  → Rust gptimage-gateway-rs :8013
       · OpenAI JSON 形状 / 并发 Semaphore / preferred email
       · HELPER_URL=http://127.0.0.1:19001
  → Python protocol_bridge :19001
       · curl_cffi + Sentinel/PoW + SSE/poll
       · 只读挂载 /root/gptimage {api,services,utils,data,config}
  → Webshare sticky → ChatGPT upstream

生产 chatgpt2api-local :8012 并行存在，互不替换。
```

环境变量（常用）：

| 变量 | 默认 | 含义 |
|------|------|------|
| `GATEWAY_LISTEN` | `0.0.0.0:8013` | Rust 面 |
| `HELPER_URL` | `http://127.0.0.1:19001` | helper |
| `HELPER_LISTEN` | `127.0.0.1:19001` | helper bind |
| `PIN_ACCOUNT_FILE` | secrets/pin… | 默认 pin |
| `IMAGE_GLOBAL_CONCURRENCY` | `3` | Rust 生图闸 |
| `MVP_MIN_IMAGE_QUOTA` | `1` | 额度门 |
| `MVP_FORCE_POOL_STICKY` | off | 强制号池 sticky |

---

## 4. 仓布局

```text
gptimage-gateway-rs/
  plan.md                 ← 本文件（进度 + 路线）
  bin/gptimage-gateway-rs ← linux amd64 发布产物
  crates/{gateway,protocol,helper_client}
  helper/{protocol_bridge.py,openai_face.py}  # face 为过渡；现网 Rust 优先
  scripts/panda_bringup_rust_face.sh
  scripts/mvp_rust_conc_matrix.py
  docs/00 · 13 · 17 · 18
  deploy/test-compose.example.yml
  data/runlogs/
```

---

## 5. 部署与回滚（测试环）

```bash
# 本地/WSL（禁止 panda 编译）
cargo build --release -p gateway
cp target/release/gptimage-gateway-rs bin/
git push

# panda
cd /root/gptimage-gateway-rs && git pull --ff-only
bash scripts/panda_bringup_rust_face.sh
curl -fsS http://127.0.0.1:8013/health   # runtime=rust
curl -fsS http://127.0.0.1:19001/health
```

回滚：停 Rust 进程 + `docker rm -f gptimage-gateway-rs-helper`；可临时 `panda_bringup_mvp_face.sh` 回 Python face。**不影响** `:8012`。

---

## 6. 晋级检查表

- [x] L0：契约 + 仓骨架
- [x] Phase A：MVP crate + helper + Panda `:8013` 接线
- [ ] Phase A 出门：CF 可测窗 + 生图矩阵签字（`self=0`，健康延迟）
- [ ] Phase B：edits / estuary / fixtures
- [ ] Phase C：选号 / admission
- [ ] Phase D：RCA / 指标对齐
- [ ] Phase E / R2：生产立项

## 7. 关联

- CF / egress（**Owner：号池侧**）：`../gptimage/docs/17-cf403-and-egress.md`
- 生产基线：`../gptimage/docs/13-performance-and-rewrite-estimate.md`
- 协议差距 / 纯 HTTP：`../gptimage/docs/12` · `20`
- 指针：`../gptimage/docs/14-rust-rewrite-plan.md`
- 操作：`docs/17-operator-guide.md` · 矩阵：`docs/18-test-matrix.md`
