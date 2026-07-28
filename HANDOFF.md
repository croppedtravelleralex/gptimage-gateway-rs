# HANDOFF — gptimage-gateway-rs

最后更新：2026-07-28（**L1–L5 本地闭环；总进度 ≈99%**）

## 📌 部署策略（2026-07-28 决议）

| 原则 | 说明 |
|------|------|
| **本地实现为主** | WSL：`UPSTREAM_ONLY=1 bash scripts/local_bringup_wsl.sh` + `local_smoke_upstream.sh` |
| **默认数据面** | `DATA_PLANE=upstream`（chat/image 不经 Python helper） |
| **不在 Panda 迭代** | `:8013` 已退役；完整后**独立上线** |
| **Panda 仅只读辅助** | 导号 `export_pin_account.py`、一次性探针（可选） |

`scripts/panda_bringup_rust_face.sh` **已禁用**（执行即 exit 1）。

## ✅ 编译与门禁：全绿

```bash
cargo build --workspace        # ✅
cargo test --workspace         # ✅（含 upstream 11 + workspace 合计）
cargo fmt --all -- --check     # ✅
cargo clippy -- -D warnings    # ✅
python scripts/check_runlog_desense.py  # ✅
```

CI：`.github/workflows/ci.yml` + **GHCR** `.github/workflows/publish-gateway.yml`（`main` push → `ghcr.io/croppedtravelleralex/gptimage-gateway-rs`）。

## 🎯 里程碑：Rust 数据面首次 Panda 实网出图

**2026-07-28** 在 Panda 用 `upstream-probe`（号池导号 + 绑定代理）跑通：

| 步骤 | 结果 |
|------|------|
| Sentinel 开票（PoW + Turnstile + finalize） | ✅ `REQUIREMENTS_OK` |
| 生图 prepare | ✅ `IMAGE_PREPARE_OK` |
| 生图 SSE → `file_id` | ✅ `IMAGE_READY`（~40s，8 events） |

详情与命令：[docs/30-phase1-probe-panda.md](docs/30-phase1-probe-panda.md)。

**意义**：`crates/upstream/` 已实网验证。**后续在本地把 gateway + upstream 接完整，再独立上线**；不在 Panda `:8013` 上迭代。

## ⚠️ 上线前不做的事

| 事项 | 状态 |
|------|------|
| Panda `:8013` gateway/helper | **已停并退役**（2026-07-28） |
| gateway 接线到 `upstream`（在 Panda 上） | **不做** —— 本地完成后再说 |
| 替换 / 影响生产 `:8012` | **禁止** |

## 🎯 Phase B′ 判据 1 通过 —— 硬阻塞降级

`wreq` 实测能复现 curl_cffi 的 TLS 指纹（JA3N / JA4 / JA4_r / Akamai 逐字节一致，
chrome124 / chrome131）。详见 [docs/27](docs/27-tls-fingerprint-spike-20260726.md)。

**「数据面重写」的性质从「技术未知」变为「工作量」。** 但判据 2（CF 通过率）仍未测 ——
指纹一致 ≠ 能过 CF。

## 读什么

0. [SOURCE.md](SOURCE.md) — **重写对照基准**：`../gptimage-panda`（⚠️ 漏 4 份文档）
1. [docs/25-panda-vs-rust-20260726.md](docs/25-panda-vs-rust-20260726.md) — **生产现采对照**
2. [docs/26-perf-measured-20260726.md](docs/26-perf-measured-20260726.md) — **性能实测**（98.5% CPU 归因）
3. [docs/27-tls-fingerprint-spike-20260726.md](docs/27-tls-fingerprint-spike-20260726.md) — **TLS 指纹实测**（B′ 判据 1）
4. [docs/22-audit-2026-07-26.md](docs/22-audit-2026-07-26.md) — **全量审计**（含修复状态）
5. [docs/23-rewrite-progress.md](docs/23-rewrite-progress.md) — **进度量化**（六口径）
6. [docs/24-gap-inventory.md](docs/24-gap-inventory.md) — **能力 gap 全量清单**
7. [plan.md](plan.md) — 进度 + Phase A→E 路线
8. [docs/30-phase1-probe-panda.md](docs/30-phase1-probe-panda.md) — **第一期 Panda 探针验证**（文本 SSE + 生图探针）
9. [docs/21-auth-and-ui.md](docs/21-auth-and-ui.md) — 鉴权、Web UI、环境变量
10. [docs/28-decisions-20260727.md](docs/28-decisions-20260727.md) — **架构决策**（§6.3 六项，以 Panda 为准）
11. [docs/00-contract.md](docs/00-contract.md) — 协议契约 / error_class
12. [docs/18-test-matrix.md](docs/18-test-matrix.md) — 验收矩阵
13. [docs/17-operator-guide.md](docs/17-operator-guide.md) — 拓扑与故障树

## 当前状态

- **部署**：**本地 WSL 全栈**为主；Panda `:8013` **已退役**
- **Phase A（旧）**：Panda `:8013` MVP —— **取消**，不再维护
- **Phase A+**：鉴权 + `web/` —— **本地** `LOCAL_MODE=full`
- **Phase B 数据面**：`upstream` 探针 Panda 签字 ✅；**gateway 已接 upstream**（`DATA_PLANE=upstream`）
- **总进度（本地可验收）**：**≈ 99%** —— 见 [docs/23](docs/23-rewrite-progress.md) L0–L5
- **数据面移植（旧口径）**：**≈ 32%**
- **号源**：Panda 只读导号；禁止本地注册

### 新增 crate（2026-07-28）

| crate | LOC | 职责 |
|-------|-----|------|
| `crates/upstream/` | ~2,423 | wreq TLS、PoW、Turnstile VM、Sentinel、SSE、生图 prepare/start |
| `crates/upstream-probe/` | ~279 | 分步探针（tls/bootstrap/requirements/sse/image） |

### ⚠️ 供应链缺口（未解决）

「已部署 5.4%」大于「已进 git 2.9%」不是笔误 —— **生产上跑着 598 行没有进任何 git 仓的 Rust**：

| 事实 | 依据 |
|------|------|
| 路径 A 的 `dispatch_gate`/`lease_pool`/`sediment`/整个 `image_schedule_trace/` 在 `../gptimage` 里全是 `??` | `git status crates/` |
| 这些代码**正在生产路径上执行** | `slot_ledger.py:268-277` 检测 `native/*.so` 即切 rust 后端 |
| `libimage_schedule_core.so` 已挂载进生产，但 **panda 上没有它的源码** | `find /root/gptimage/crates` |
| 该 crate 曾在 **panda 上编译过**（铁律一历史违规） | `crates/*/target/{debug,release,x86_64-*}` |

## 简易后端 API 快查

| 能力 | 路径 | 角色 |
|------|------|------|
| 登录/登出/me | `/api/auth/*` | 见 21 文档 |
| 后端能力 | `GET /api/backend/capabilities` | 公开 |
| 对话 | `POST /v1/chat/completions` | member + admin |
| 号池/额度 | `/v1/accounts/candidates` `/v1/quota*` | admin |
| 用户管理 | `/api/admin/users` | admin |
| 生图 | `/v1/images/*` | **IMAGE_ENABLED=1** 时走 upstream（`DATA_PLANE=upstream`）或 helper 降级路径 |

## 下一步

**P0 —— 已全部完成 ✅**

| # | 事项 | 做法 |
|---|------|------|
| 1 | `ticket_pool` 编译失败 | 删 `Serialize`/`Deserialize` derive（纯内存池不需要），一并堵住明文 token 泄露；顺带修正反了的复用守卫语义 |
| 2 | CORS 构造 panic | `cors_layer_from()` 读 `GATEWAY_CORS_ORIGINS`；无 allowlist 时降级为无 credentials |
| 3 | bringup 默认值 | 默认 loopback + `AUTH_DISABLE=0` + `IMAGE_ENABLED=0`；主动拒绝「无鉴权 + 非 loopback」组合 |
| 4 | helper 无鉴权吐凭据 | `X-Helper-Token` 共享密钥，**未设时 fail closed**；candidates 剥离 token 与代理口令 |
| 5 | 默认 admin 口令 / 默认 JWT secret | 双双改 `bail!`；口令加 12 字节下限 |
| 6 | 建 CI | `.github/workflows/ci.yml` 四道门禁 |
| 7 | 清凭据 | 删 19 个死脚本（含 7 个带真实邮箱）；`bin/` 出 git；`.gitignore` 补 5 类 |

**P1（下一批）** —— ✅ 2026-07-27 本地闭环（未 push）

1. ~~**提交这 1,764 行**~~ ✅ 2026-07-27 已提交（含 `web/`、CI、auth、fixtures、`docs/21`–`28`）
2. ~~Phase B 契约重做~~ ✅ Python `capture_protocol_fixtures.py` + `spa_tool_path` 分支 + 8 项 fixture diff 全绿
3. ~~`jti` 吊销表~~ ✅ `002_revoked_jti.sql` + logout 吊销 + `revoked_jti_rejects_token` / `logout_revokes_jti_session`
4. ~~Phase B′ 判据 2 框架~~ ✅ `scripts/cf_pass_rate_ab.py` + [docs/29](docs/29-cf-pass-rate-ab-20260727.md)（实测需 CF 窗口 + `SPIKE_PROXY`）
5. ~~**对齐 Panda 鉴权**~~ ✅ `AuthMode` + `GATEWAY_AUTH_KEY` + `PANDA_ALIGN=1` bringup（JWT/Web UI 仍为增强，见 [docs/28](docs/28-decisions-20260727.md) §1.4）

**当前波次：L3 本地 E2E**（见 [docs/23](docs/23-rewrite-progress.md)）

| 阶段 | 进度 | 下一步 |
|------|------|--------|
| L0 工程基线 | 100% | — |
| L1 upstream | 100% | — |
| L2 gateway 接线 | 100% | — |
| L3 本地全栈 E2E | 98% | 可选并发矩阵补测 |
| L4 收尾 | 90% | CF AB 实测窗口 |
| L5 独立上线 | 90% | R2 canary（另立项） |

**已取消**：Panda `:8013`、半成品接线上 Panda

## 本地命令（WSL 全栈）

```bash
# 1) 一次性：helper Python 依赖
bash scripts/setup_wsl_helper_deps.sh

# 2) 在 Panda 导号：scripts/export_pin_account.py → secrets/pin_account.json（禁止本地注册/手工 token）

# 3) 全栈启动（默认 LOCAL_MODE=full：JWT + IMAGE_ENABLED=1 + DATA_PLANE=upstream）
bash scripts/local_bringup_wsl.sh

# 仅 gateway（无 helper，upstream 模式推荐）
UPSTREAM_ONLY=1 bash scripts/local_bringup_wsl.sh

# 4) 验收
bash scripts/local_smoke_upstream.sh
IMAGE_ENABLED=1 bash scripts/local_smoke_upstream.sh   # 含生图腿（UPSTREAM_IMAGE_TIMEOUT_SECS=90）
bash scripts/local_smoke_full.sh                     # helper 路径遗留验收

# 仅 API 冒烟（无 UI / 无鉴权）
LOCAL_MODE=minimal bash scripts/local_bringup_wsl.sh
IMAGE_SMOKE_EXPECT=501 bash scripts/local_smoke.sh

cargo test --workspace
```

浏览器打开 `http://127.0.0.1:8013/`，管理员账号见 `secrets/local_admin_password`。

**LOCAL_MODE=full 包含**：release 编译、Next.js 静态导出、`GATEWAY_STATIC_DIR`、JWT bootstrap、生图开关、`DATA_PLANE=upstream`。

**`UPSTREAM_ONLY=1`**：仅启动 gateway，跳过 helper docker/python（chat/image 经 Rust upstream）。

**`LOCAL_MODE=minimal`**：仍启动 helper（向后兼容旧 smoke 路径）。

## 本地命令（开发单项）

```bash
HELPER_INTERNAL_TOKEN=$(openssl rand -hex 32) \
AUTH_JWT_SECRET=$(openssl rand -hex 32) \
AUTH_BOOTSTRAP_ADMIN_USER=admin \
AUTH_BOOTSTRAP_ADMIN_PASSWORD='at-least-12-chars' \
PIN_ACCOUNT_FILE=secrets/pin_account.json \
./target/release/gptimage-gateway-rs
```

## 禁止

- Panda 上 `cargo build` / `docker build`
- secrets 进 git；未授权成员访问 admin 路由
- 未立项改生产 Nginx / `:8012`
- 新增 `scripts/_tmp_*.py`（19 个已清理完毕，别再攒）
- 提交 `spike/` 下的 BoringSSL 产物与 `libclang.dll`（已在 `.gitignore`）
