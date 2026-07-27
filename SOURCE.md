# 非 Rust 版本来源（对照实现）

本仓是 **Rust 重写的独立项目**。业务行为与协议形状以同级 **Python 生产仓** 为准，不是从零发明。

## 来源路径

| 环境 | 路径 | 角色 |
|------|------|------|
| **生产快照**（2026-07-26 拉取） | `../gptimage-panda` | **重写对照基准**（真相源） |
| 本地开发树 | `../gptimage`（`AutoRegister/gptimage`） | 领先生产 19 个提交；helper 运行时挂的是它 |
| Panda 运行树 | `ssh panda:/root/gptimage` | 生产原址；容器内常见挂载为 `/app` |
| 生产进程 | Docker `chatgpt2api-local`，宿主机端口 **`:8012`** | — |

### 为什么有两棵树

`../gptimage` 是本地开发树，git HEAD 领先生产 19 个提交、另有 429 项未提交变更；
`../gptimage-panda` 是 2026-07-26 从生产机拉下的工作区快照（HEAD `3166710` @ 2026-06-13 + 308 项未提交）。

**重写对照以 `../gptimage-panda` 为准** —— 它是 `:8012` 实际在跑的代码。

### 两树差异（已逐文件核对）

`services/` + `api/` + `utils/` 共 118 个 `.py`，归一化行尾后：**115 个内容相同**，2 个不同，1 个仅生产有。

| 文件 | 差异 |
|------|------|
| `services/image_pipeline/guards.py` | 本地较新（conc10 修复：`ready`/`schedulable` 取代 `dispatchable`）；**生产未收到**，仍会在 inflight 饱和时误报 `image pool starved` |
| `services/yumail_otp.py` | 非数据面（OTP，永久非目标） |
| `services/register/domain_intel.py` | 仅生产有；注册机，永久非目标 |

**协议层与上游 API 全部逐字节一致**，因此 [docs/22](docs/22-audit-2026-07-26.md) §3 基于本地树得出的
「契约漂移 17 字段」判定对生产同样成立。

### ⚠️ 快照的文档面不完整（2026-07-26 晚发现）

代码面已逐文件核对无误，但**文档面漏了 4 份** —— panda `/root/gptimage/docs/` 有 9 个 `.md`，
本快照只有 5 个，缺的恰是唯一 4 份带当期审计结论的：

| 缺失文件 | 行数 |
|---------|------|
| `04-improvement-backlog.md` | 481 |
| `28-scheduling-queue-slot-audit-20260726.md` | 422 |
| `27-pipeline-watchdog-monitoring-matrix.md` | 90 |
| `README.md` | 52 |

共有的 5 份内容零漂移（9/44/124/271/363 行，mtime 均 6-16）。

**影响**：以本快照为分母的 [docs/23](docs/23-rewrite-progress.md) / [docs/24](docs/24-gap-inventory.md)，
**代码部分口径有效，文档部分口径待复核**。需要时直接读 panda 或 `../gptimage/docs/`（后者有 38 份）。

反向问题：panda 的 `docs/README.md` 是从 Windows 同步过去的，索引里 12 个目标文件/目录
在 panda 上**全部不存在** —— panda 的文档导航整体失效。详见 [docs/25](docs/25-panda-vs-rust-20260726.md) §2.2。

> ⚠️ `../gptimage-panda/` 含真实凭据（`config.json` 的 `auth-key`、`proxy_list.json` 的内联代理口令）。
> 该目录不在任何 git 仓内，**请保持这一点**。详见其 `_README-PULLED.md`。

## 来源是什么

- **项目名 / 运行名**：`gptimage` / `chatgpt2api`（Python 3.12 + FastAPI + curl_cffi）
- **角色**：当前**生产** ChatGPT 逆向数据面（文本 / 生图 / 号池 / 调度 / 运维）
- **本仓关系**：只对照、只复用协议与 helper 侧能力；**不**把本仓当生产；公网切流另立项（R2）

## 本仓如何挂上来源

Phase A 的 Python helper（`:19001`）在 Panda 上**只读挂载**来源树中的：

- `api/` · `services/` · `utils/` · `scripts/` · `config.json` · `data/`

Rust face（`:8013`）编排 HTTP；出站 TLS / PoW / SSE 仍走上述 Python 实现。

## ⚠️ 来源树里已经有 Rust

`../gptimage/crates/` 下有两个已编译并**部署到 panda 生产**的 Rust crate（`native/*.so`，2026-07-25）：

| crate | 行数 | 已进 git | 覆盖 | panda 上 |
|-------|------|---------|------|---------|
| `image_schedule_core` | 597 | 509 | 双槽账本（account+sS）/ 调度门 / 租约池 / sediment 抽取 | 只有 `.so`，**无源码** |
| `image_schedule_trace` | 510 | **0** | 21 事件调度追踪 + 11 阶段耗时模型 | 源码 + `.so` |

`services/image_pipeline/slot_ledger.py:268-277` 有 `_PySlotLedger` / `_RustSlotLedger` 双实现 +
`SlotLedgerFacade` 选后端 —— 检测到 `native/*.so` 即返回 `backend == "rust"`，经 ctypes 加载。
**2026-07-26 确认这条路径在生产上是活的，非死代码。**

**二者都声明了 `crate-type = ["cdylib", "rlib"]`，本仓可直接 `path` 依赖复用，绕开 FFI 层。**
本仓当前对它们零引用，且 `crates/ticket_pool` 与 `pre_ticket_pool.py` 重叠 80% —— 详见
[docs/24-gap-inventory.md](docs/24-gap-inventory.md) §3。

> ⚠️ **1,107 行中只有 509 行进了 git** —— `dispatch_gate.rs`、`lease_pool.rs`、`sediment.rs`、
> 整个 `image_schedule_trace/` 在 `../gptimage` 里全是 `??`。即**生产上跑着 598 行未入库 Rust**，
> 且 `libimage_schedule_core.so` 在 panda 上找不到对应源码，无法溯源到任何 commit。
> 见 [docs/25](docs/25-panda-vs-rust-20260726.md) §1.5。

## 重写对照速查

| 要移植的能力 | 真相源（`../gptimage-panda/`） | 行数 |
|-------------|------------------------------|------|
| 协议构造（prepare/start body） | `services/protocol/chatgpt_web_request.py:309-439` | 439 |
| 上游 API（TLS 指纹 / PoW / SSE / upload / estuary） | `services/openai_backend_api.py` | 4781 |
| SSE 解析与 ready 谓词 | `services/protocol/conversation.py` | 2325 |
| 生图编排 / 槽位 / 票池 | `services/image_pipeline/` | 2371 |
| **异步图片队列 + 槽位释放** | `services/image_task_service.py` | 2456 |
| 号池选号与 slot 记账 | `services/account_service.py` | 4177 |
| 代理绑定 / sticky / CF 转移 | `services/proxy_service.py` + `proxy_cf_*.py` | ~1500 |
| 拟人化调度 / 工作负载策略 | `services/humanlike_scheduler.py` + `account_workload_policy*.py` | 718 |

分母定义与进度口径：[docs/23-rewrite-progress.md](docs/23-rewrite-progress.md)
能力 gap 全量清单：[docs/24-gap-inventory.md](docs/24-gap-inventory.md)

## 文档指针

- 来源仓施工/状态：`../gptimage-panda/docs/`（尤其 `02` · `12` · `13` · `17`）
- 生产快照说明：`../gptimage-panda/_README-PULLED.md`
- 本仓路线：`plan.md`
