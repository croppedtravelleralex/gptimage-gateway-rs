# 独立部署指南（upstream-only）

最后更新：2026-07-28

> **策略**：本地 WSL 完成实现与验收 → 通过 git 链路发布 → **独立端口**上线。  
> **红线**：**不得**影响、替换或重启生产 `:8012`（`chatgpt2api-local`）。

## 1. 本地优先完整验收清单

在推镜像或上独立机之前，本地应全部打勾：

| # | 项 | 命令 / 判据 |
|---|-----|------------|
| 1 | 编译 | `cargo build -p gateway` ✅ |
| 2 | 测试 | `cargo test -p gateway` ✅ |
| 3 | workspace 门禁 | `cargo fmt --all -- --check` / `cargo clippy -- -D warnings` |
| 4 | 号源 | `secrets/pin_account.json` 含有效 `access_token` + `proxy` |
| 5 | 启动 | `UPSTREAM_ONLY=1 bash scripts/local_bringup_wsl.sh` |
| 6 | 健康 | `curl -s localhost:8013/health` → `"ok":true` |
| 7 | 能力 | `curl -s localhost:8013/api/backend/capabilities` → `chat_stream`/`stream_chat` true，`data_plane":"upstream"` |
| 8 | 非流式对话 | `bash scripts/local_smoke_upstream.sh` 或手动 `POST /v1/chat/completions` |
| 9 | 流式对话 | `POST /v1/chat/completions` + `"stream":true` → `text/event-stream` + `data: [DONE]` |
| 10 | 生图 | `IMAGE_ENABLED=1` 时 `POST /v1/images/generations` 返回 b64 |
| 11 | 脱敏 | `python scripts/check_runlog_desense.py` |

本地默认端口 **8013**（`GATEWAY_LISTEN`）；独立部署默认 **8014**，避免与历史 MVP 或 `:8012` 混淆。

## 2. 独立部署步骤

### 2.1 发布链路（铁律）

```text
本地改测 → git commit → git push → GitHub Actions → GHCR
→ 目标机: git pull + docker compose pull && up
```

禁止在 Panda 上 `cargo build` / `docker build` / `scp` 二进制。

### 2.2 目标机准备

```bash
mkdir -p /root/gptimage-gateway-rs/secrets
# 从 Panda 只读导号（示例）：
# python scripts/export_pin_account.py > /root/gptimage-gateway-rs/secrets/pin_account.json
chmod 600 /root/gptimage-gateway-rs/secrets/pin_account.json
```

### 2.3 Compose 启动

使用 [`deploy/independent-compose.yml`](../deploy/independent-compose.yml)：

- **单服务**：仅 `gateway`，无 `helper`
- **网络**：`network_mode: host`
- **数据面**：`DATA_PLANE=upstream`
- **生图**：`IMAGE_ENABLED=1`
- **密钥**：`pin_account.json` 只读挂载

```bash
cd /root/gptimage-gateway-rs
git pull
docker compose -f deploy/independent-compose.yml pull
docker compose -f deploy/independent-compose.yml up -d
```

### 2.4 验收（独立端口，默认 8014）

```bash
curl -s localhost:8014/health | jq .
curl -s localhost:8014/api/backend/capabilities | jq '.features'
# 流式
curl -N localhost:8014/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <key-or-cookie>' \
  -d '{"model":"gpt-4o-mini","stream":true,"messages":[{"role":"user","content":"ping"}]}'
```

### 2.5 可选：鉴权与静态 UI

独立栈默认无 `AUTH_DISABLE=1`（与已退役的 `:8013` MVP 不同）。若需 JWT + Web UI：

- 设置 `AUTH_DISABLE=0`、`JWT_SECRET`、`GATEWAY_STATIC_DIR`
- 构建 `web/out` 并挂载或 bake 进镜像  
详见 [21-auth-and-ui.md](21-auth-and-ui.md)。

## 3. 回滚

```bash
docker compose -f deploy/independent-compose.yml down
# 或 pin 到上一版镜像 tag：
# image: ghcr.io/.../gptimage-gateway-rs:<previous-sha>
docker compose -f deploy/independent-compose.yml up -d
```

回滚仅影响 **独立端口**（如 8014）。**不要**修改 `chatgpt2api-local`、Nginx 上游或 `:8012` 路由。

## 4. 与 :8012 的关系

| 服务 | 端口 | 状态 |
|------|------|------|
| `chatgpt2api-local` | **8012** | 生产 Python 主面 — **不动** |
| 本仓独立 gateway | **8014**（建议） | upstream-only，另立项切流 |
| 历史 MVP `:8013` | 8013 | **已退役**（2026-07-28） |

切流到独立 Rust 面是 **R2** 决策，不在本清单范围内。

## 5. 故障排查

| 现象 | 检查 |
|------|------|
| `502 text_stream_failed` | 号池 token / 代理；`RUST_LOG=debug` |
| `capabilities` 无 `stream_chat` | 确认 `DATA_PLANE=upstream` 且镜像版本 ≥ 含流式接线 |
| 生图 403/503 | `IMAGE_ENABLED=1`；额度与 CF 见 [17-operator-guide.md](17-operator-guide.md) |
| helper 相关错误 | 独立 compose **不应**启动 helper；检查 `DATA_PLANE` |

## 6. 相关文档

- [HANDOFF.md](../HANDOFF.md) — 部署策略总览
- [23-rewrite-progress.md](23-rewrite-progress.md) — L5 独立上线阶段
- [30-phase1-probe-panda.md](30-phase1-probe-panda.md) — upstream 探针签字记录
- [28-decisions-20260727.md](28-decisions-20260727.md) — 架构决策
