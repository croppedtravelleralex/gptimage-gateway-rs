# Changelog — gptimage-gateway-rs

## Unreleased

+ [文档] 2026-07-22：同步 Rust Phase A 进度与 Phase A→E 重写路线——`plan.md` / `README` / `HANDOFF` / `docs/17` / `docs/18`；CF403 明确归号池/egress（gptimage `17`），不阻塞接线认定、阻塞 MVP 正式签字。
+ [功能] 2026-07-21：Rust face 接管 `:8013`——`gptimage-gateway-rs` 编排 OpenAI HTTP + `IMAGE_GLOBAL_CONCURRENCY` 信号量；Python `protocol_bridge` 仅侧车 `:19001`（curl_cffi/PoW/SSE）。目标：1/3 并发文生图单张 40–60s。
+ [修复] 2026-07-21：helper 默认 `make_backend` 直连（`MVP_FORCE_POOL_STICKY` 才走号池 sticky）；避免独立进程 `get_available_access_token` sticky 失败后落到空 ready（`no available image quota`）。
+ [功能] 2026-07-21：helper `GET /v1/internal/accounts/candidates`；Rust `X-Preferred-Account-Email` + 启动时种子号池；`scripts/panda_bringup_rust_face.sh` / `mvp_rust_conc_matrix.py`。
+ [部署] 2026-07-21：私有仓 `croppedtravelleralex/gptimage-gateway-rs`；linux amd64 产物 `bin/gptimage-gateway-rs`；panda `/root/gptimage-gateway-rs` git pull + bringup（生产 `:8012` 不动）。
+ [修复] 2026-07-21：纠正 CF 归因——对照生产后，MVP 自研问题是绕过 `get_available_access_token` 槽位 + 生图强制 `_bootstrap()`；已改为 `pool_sticky` 取号并 `_ensure_bootstrap()`。A/B 当时生产同步生图同样出现 CF/挂起，并非「多 IP 并发必然 CF」。
+ [功能] 2026-07-21：`:8013` 多号——`X-Preferred-Account-Email` 从号池解析（独立 proxy）；`GET /v1/accounts/candidates`；同号锁、异号可并行。单 pin 默认路径不变。
+ [验证] 2026-07-21：多号并发=2——独立出口已生效；健康号成功 ~36–38s；同波次另一路常 CF403 / wall_timeout。全量 4 号并发曾 0/4（上游 CF）。`self=0`。
+ [验证] 2026-07-21：并发=2 矩阵（同 pin）——第1轮 2/4（成功 ~31s，失败 CF403）；第2轮 stagger=3s 仍 1/4（成功 44s，其余 CF403）；`self=0`。结论：同代理并发易触发上游 CF，不作为出门 blocker，并发需多号/多出口。
+ [修复] 2026-07-20：串行挂死 RCA——`post_ready=null` 时客户端 75s 超时后服务端 SSE 可僵死 ~1772s；补 `post_ready=50` + `cancel_event` 墙钟 70s + 重启清僵尸。串行 2/2：45.5s / 50.9s（额度 21→19）。
+ [修复] 2026-07-20：生图 SSE 见到 `file_id` 即结束（`complete_predicate`），避免等 EOF ~90s；MVP 默认 `post_ready=null`+`poll≤25`+客户端 75s。单图实测 ~63s / `self=0`（额度先读）。
+ [验证] 2026-07-20：Panda `:8013` 1+1 矩阵绿——`qaflowfbdb3ovksr@proton.me` text 6.7s / image 99.6s / remaining=23 / `self=0` / `pass_gate=true`（`rust-mvp-fixed-20260720-220907.json`）。客户端超时压到 ~100s，禁止 600–720s 硬等。
+ [修复] 2026-07-20：face 层额度检查后 `skip_quota_gate`，避免生图前双次 `get_user_info`；panda `image_sse_post_ready_timeout_secs=null`（池身份稳定后再议安全阀）。
+ [功能] 2026-07-20：MVP 额度门禁——`/v1/quota`/`/v1/quota/refresh` 走 `get_user_info` 实时刷新；生图前 `remaining>=MVP_MIN_IMAGE_QUOTA` 才继续，否则 `429 fault=quota`；matrix 不足额跳过生图。
+ [修复] 2026-07-20：生图 SSE `iter_lines` 补齐 `post_ready` 安全阀；MVP poll 默认压到数十秒，超时明确 502。
+ [修复] 2026-07-20：MVP `make_backend` 优先用账号池完整身份（fp/proxy）；pin 裸注入会导致 SSE 挂死、`tool_invoked=null`。池身份后单图约 41s 成功。
+ [文档] 2026-07-20：对照刷新——Python 基线文本 3/4、生图 3/4（self=0）；见 gptimage `docs/13` 与 Panda `rust-baseline-retry-20260720-173225.json`。
+ [文档] 2026-07-20：仓初始化（README/HANDOFF/plan、docs/00·13·17·18、fixtures 约定、deploy 测试 compose 样例）。两波：MVP 生文/生图 → Panda `:8013` → 全量含 RCA；永久非目标：注册机与 FlareSolverr。
