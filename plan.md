# gptimage-gateway-rs 施工总控

最后更新：2026-07-20  
状态：**MVP 最小单位已绿**（`:8013` 1+1 `self=0`；额度门禁+池身份；Rust gateway 本地可编；下一步 5+5 短超时矩阵）  
对照生产：`../gptimage`（Panda `chatgpt2api-local:8012`）

## 0. Contract

### 目标

- 独立新项目重写 ChatGPT 逆向**数据面**，提升同机并发与稳态资源；**端到端生图不以变快为 KPI**。
- 两波推进：**MVP 最小生文/生图单位 → Panda 隔离测通 → 全量（含 RCA 运维范围）**。

### 非目标（永久）

| 项 | 说明 |
|----|------|
| 注册机 | 不迁、不测；号源外置 |
| FlareSolverr / 全局 clearance | 不引入；生产已 `clearance.enabled=false` |
| 维护环 / Outlook OTP / Panda sync UI | 首期不做 |
| 生产 `8012` / 公网切流 | 另立项 R2 |

### 红线

- `self`（非上游）失败率必须 **= 0** 才可晋级
- estuary 下载必须主 session + Bearer
- SSE ready = payload 含 `conversation_id`（禁止 `post_ready=15s`）
- `skipped_mainline` ≠ 换号失败
- 禁止 Panda `cargo build`；禁止 scp 当正式发布
- 满载语义：429，禁止空 `data` / `object=image.task` 假成功

---

## 1. 两波路线

```text
MVP 协议单位 → Panda :8013 生文/生图矩阵 → 全量(选号+RCA) → R2 生产 cutover(另立项)
```

### 波次 1 — MVP

| 单位 | 对照 Python | 要点 |
|------|-------------|------|
| U-Text-Body / U-Text-SSE | `chatgpt_web_request` / `stream_conversation` | Temporary Chat；PoW/Turnstile；Arkose 硬失败 |
| U-Img-Prepare / SSE / Poll | `_stream_picture_conversation` | ready=`conversation_id` |
| U-Img-Upload / Edit | `_upload_image` + edit body | 与 generations 同级 |
| U-Img-Estuary | `download_image_bytes` | Bearer；负例必须失败 |
| HTTP | `/v1/chat/completions`、`/v1/images/generations|edits`、`/v1/quota[/refresh]` | 固定 token，**不经选号池**；生图前必须 live 额度 `imageable` |
| 出站 | curl_cffi helper | 本机 HTTP；未证明前禁止纯 rustls 直连 |
| 额度 | `get_user_info` / conversation/init | `remaining>=MVP_MIN_IMAGE_QUOTA`（默认 1）；不足 → `429 fault=quota`，禁止硬测生图 |

**Panda MVP 出门**（详见 [docs/18-test-matrix.md](docs/18-test-matrix.md)）：

- 隔离 compose，宿主机例 `:8013`，与生产 `:8012` 并存
- 生文 ≥5、生图 ≥5；`self=0`；脱敏 runlogs
- **未出门禁止全量模块与生产 canary**

### 波次 2 — 全量（MVP 通过后）

| 模块 | 要求 |
|------|------|
| 选号 / inflight / admission | 经控制面 HTTP；硬超时/迟到 acquire 回归 |
| SCHED-001 breakdown | 空池可归因 |
| RCA / `/api/ops` / L2 agent | **纳入范围**；优先 UI 留 Python，指标/`error_class` 与 Rust 对齐；子里程碑 F-RCA 可迁 Agent |
| llm_ops | 字段与数据面统一枚举 |
| 风控拟人看板 / risk_audit | 读 Rust 计数；巡检默认可仍 OFF |
| nurture | 依赖文本单位；禁假聊 |
| 注册 / FlareSolverr | **不做** |

---

## 2. 仓布局（约定）

```text
gptimage-gateway-rs/
  plan.md
  docs/00-contract.md
  docs/13-perf-baseline-compare.md
  docs/17-operator-guide.md
  docs/18-test-matrix.md
  fixtures/protocol/          # golden JSON（自 Python 导出）
  crates/                     # 后续：gateway / protocol / helper_client
  deploy/test-compose.example.yml
  scripts/                    # 脱敏检查、对照跑法
  data/runlogs/               # 本地对照；禁 secret
```

`PROTOCOL_CONTRACT_VERSION`：见 `docs/00-contract.md`（Breaking 双边 CHANGELOG）。

---

## 3. 部署与回滚（测试环）

- 产物：CI `linux/amd64` 二进制或镜像 → artifacts → panda **测试** compose pull
- 回滚：停测试容器即可；**不影响** `:8012`
- 生产切流：R2 另立项（Python 抽样或 Nginx，须矩阵签字）

---

## 4. 晋级检查表

- [ ] L0：契约 + fixtures 目录约定 + STORE S1/L1（实打前）
- [ ] MVP crate + helper
- [ ] Panda `:8013` MVP 矩阵签字（`self=0`）
- [ ] 全量选号/admission
- [ ] 全量 RCA/指标对齐矩阵
- [ ] R2 生产立项（≥观察窗）

## 5. 关联

- 生产基线：`../gptimage/docs/13-performance-and-rewrite-estimate.md`
- 协议差距：`../gptimage/docs/12-protocol-gap-vs-web.md`
- 指针：`../gptimage/docs/14-rust-rewrite-plan.md`
