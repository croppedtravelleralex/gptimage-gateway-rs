# 非 Rust 版本来源（对照实现）

本仓是 **Rust 重写的独立项目**。业务行为与协议形状以同级 **Python 生产仓** 为准，不是从零发明。

## 来源路径

| 环境 | 路径 |
|------|------|
| 本地（Windows） | `D:\SelfMadeTool\AutoRegister\gptimage` |
| 相对本仓 | `../gptimage`（与本仓同级：`AutoRegister/gptimage`） |
| Panda 运行树 | `/root/gptimage`（容器内常见挂载为 `/app`） |
| 生产进程 | Docker `chatgpt2api-local`，宿主机端口 **`:8012`** |

## 来源是什么

- **项目名 / 运行名**：`gptimage` / `chatgpt2api`（Python 3.12 + FastAPI + curl_cffi）
- **角色**：当前**生产** ChatGPT 逆向数据面（文本 / 生图 / 号池 / 调度 / 运维）
- **本仓关系**：只对照、只复用协议与 helper 侧能力；**不**把本仓当生产；公网切流另立项（R2）

## 本仓如何挂上来源

Phase A 的 Python helper（`:19001`）在 Panda 上**只读挂载**来源树中的：

- `api/` · `services/` · `utils/` · `scripts/` · `config.json` · `data/`

Rust face（`:8013`）编排 HTTP；出站 TLS / PoW / SSE 仍走上述 Python 实现。

## 文档指针

- 来源仓施工/状态：`../gptimage/docs/`（尤其 `02` · `12` · `13` · `17`）
- 本仓路线：`plan.md`
