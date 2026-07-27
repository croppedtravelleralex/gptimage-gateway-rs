# HANDOFF — gptimage-gateway-rs

最后更新：2026-07-27（P0 已提交 + §6.3 六项决议闭合）

## ✅ 编译与门禁：全绿（本项目首次）

```bash
cargo build --workspace        # ✅
cargo test --workspace         # ✅ 56 passed
cargo fmt --all -- --check     # ✅
cargo clippy -- -D warnings    # ✅ 0 warning
python scripts/check_runlog_desense.py  # ✅ DESENSE_OK（清理前实测 14 处命中）
```

CI 已建：`.github/workflows/ci.yml`（rust / desense / web 三 job）。
**之前编译失败和 CORS panic 能长期活在 develop，就是因为没有闸门。**

## ⚠️ 但这些改动一行都还没上生产

| 事实 | 状态 |
|------|------|
| 代码改完并通过全部门禁 | ✅ |
| 已 commit | ✅ 2026-07-27（见 `git log`） |
| 已部署到 panda | ❌ panda 跑的仍是 2026-07-21 的 943 行旧二进制 |
| 数据面重写进度 | **未变** —— 仍是上游字节 0% |

本轮修的是**工程基线与安全**，不是数据面。不要把「已修」读成「已上线」。

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
8. [docs/21-auth-and-ui.md](docs/21-auth-and-ui.md) — 鉴权、Web UI、环境变量
9. [docs/28-decisions-20260727.md](docs/28-decisions-20260727.md) — **架构决策**（§6.3 六项，以 Panda 为准）
10. [docs/00-contract.md](docs/00-contract.md) — 协议契约 / error_class
11. [docs/18-test-matrix.md](docs/18-test-matrix.md) — 验收矩阵
12. [docs/17-operator-guide.md](docs/17-operator-guide.md) — 拓扑与故障树

## 当前状态

- **Phase A**：Panda `Rust :8013` + `helper :19001`；跑的是 commit `7c34159` 的 943 行 MVP
- **Phase A+**：鉴权 + `web/` 代码在，**未提交也未部署** → panda 上 `/api/auth/*` 全 404
- **Phase B 契约**：**判定不成立** —— 夹具自证，与生产漂移 17 字段（本轮修了 1 项：固定 UUID）
- **Phase B′**：**判据 1 通过**（TLS 指纹等价），判据 2/3/4 未测
- **端点覆盖**：生产态 **7 / 129**（本地工作树 16，新增 `/api/admin/status`）
- **数据面重写**：功能加权 12.8% / 工作树体量 8.3% / 已进 git 2.9% / **上游字节 0%**
- **性能收益**：**当前架构下仍为 0%**（Rust 出站零个指向 ChatGPT）

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
| 生图 | `/v1/images/*` | **默认 501 deferred** |

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

**P1（下一批）**

1. ~~**提交这 1,764 行**~~ ✅ 2026-07-27 已提交（含 `web/`、CI、auth、fixtures、`docs/21`–`28`）
2. Phase B 契约重做：夹具从 Python 侧真实捕获 + 全量 diff（17 项漂移只修了 1 项）
3. `jti` 吊销表 —— `require_auth` 已回查用户状态，但 logout 仍不能服务端作废 token
4. Phase B′ 判据 2：CF 通过率 A/B（用 chrome124 / chrome131，**弃用 chrome120**，见 [docs/27](docs/27-tls-fingerprint-spike-20260726.md) §2）
5. ~~**对齐 Panda 鉴权**~~ ✅ `AuthMode` + `GATEWAY_AUTH_KEY` + `PANDA_ALIGN=1` bringup（JWT/Web UI 仍为增强，见 [docs/28](docs/28-decisions-20260727.md) §1.4）

**P2**

5. Phase C：admission 进编排面 —— **先做双轨决策**
6. （跨仓）路径 A 的 598 行未入库代码补提交；`libimage_schedule_core.so` 恢复溯源
7. `wreq` 从 `-rc` 升正式版后复测指纹

**待决策（6 项）** —— ✅ 已全部闭合，见 [docs/28-decisions-20260727.md](docs/28-decisions-20260727.md)（以 Panda 现网为准）。

## 本地命令

```bash
cargo test --workspace         # 56 passed
cargo clippy -- -D warnings    # 0 warning
python scripts/check_runlog_desense.py

cd web && npm run build
```

启动需要的最小环境（缺任一项 fail-fast）：

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
