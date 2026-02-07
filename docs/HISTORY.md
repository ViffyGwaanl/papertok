# PaperTok 项目历史（已完成工作清单）

> 目的：把“我们之前做过的所有事”按可审计的方式写清楚，便于回溯与交接。

## 0) 里程碑概览

- M0：端到端 MVP 跑通（HF Top10 → PDF → MinerU → explain → captions → images → FE）
- M1：Admin Config（DB-backed）
- M2：Jobs 队列 + Worker（后台长任务）
- M3：Alembic migrations（可演进 schema）
- M4：paper_events（失败闭环与可观测性）
- P1 Ops：launchd 收口、日志轮转、路径可迁移性

---

## 1) 后端 / 前端基础
- FastAPI + SQLite（SQLModel）
- 同源单服务：后端 mount 前端 dist（避免分开部署带来的 LAN/localhost 不稳定）
- 静态挂载：
  - `/static/mineru` → `MINERU_OUT_ROOT`
  - `/static/pdfs` → `PAPERS_PDF_DIR`
  - `/static/gen` → `PAPER_GEN_IMAGES_DIR`（Seedream）
  - `/static/gen_glm` → `PAPER_GEN_IMAGES_GLM_DIR`（GLM-Image）
- 前端：WikiTok 风格竖滑 + 详情弹窗（讲解/MD/图片图注/PDF/生成图）

---

## 2) 数据一致性与 No Fake Data
- `papers.day`（YYYY-MM-DD）用于“当天 Top10”分区
- Feed 默认不展示未完成讲解论文：`feed_require_explain=True`
- 生图只针对“MinerU + explain”已完成的论文；对历史上不满足前置条件而生成的图片，采取 **disable（不删除）** 的做法

---

## 3) 双供应商生图（Seedream + GLM-Image）
- `paper_images` 表存两套 provider 输出
- provider-aware 的唯一索引，保证同一 paper/kind/provider/order_idx 不重复
- Feed 可通过 DB config 切换展示 provider：`paper_images_display_provider=seedream|glm|auto`

---

## 4) Admin（DB 配置）
- 新增 `app_settings` 表
- `GET/PUT /api/admin/config`
- `/admin` 页面可在手机端操作（响应式）

---

## 5) Jobs 系统（后台长任务）
- 新增 `jobs` 表 + `job_worker`
- Admin Jobs API：入队/列表/日志 tail/worker kick/worker logs meta+truncate
- 日志落盘：`data/logs/job_<id>_<type>.log`

已支持 job：
- `image_caption_scoped` / `image_caption_regen_scoped`
- `paper_retry_stage`
- `paper_images_glm_backfill`
- `paper_events_backfill`

---

## 6) paper_events（可观测性 + 失败闭环）
- 新增 `paper_events` 表
- 记录 stage 的 started/success/failed（以及部分场景的 skipped）
- `/api/status` 输出 failed/skipped 汇总 + recent 列表
- per-paper retry 能对失败 stage 做闭环重试

---

## 7) PDF Repair（MinerU 失败后保守修复）
- 引入 `qpdf`（Homebrew）
- 失败后修复到缓存目录 `data/raw/pdfs_repaired/`，原 PDF 不动
- qpdf 返回码 rc=3（warnings）按成功处理，避免误报

---

## 8) Alembic migrations（SQLite 可演进）
- 完整接入 Alembic
- `init_db()` 启动时自动 migrate
- 兼容“老 DB 无 alembic 版本”的 baseline stamp

---

## 9) 运维（P1）：launchd 收口 + 日志轮转 + 路径可迁移
- launchd 只保留 core 4 个 agent（server/job_worker/daily/logrotate）
- 一次性重任务从“长期 load 的 LaunchAgents”迁移到 Admin → Jobs
- `ops/run_logrotate.sh` 改为 copy+truncate（更符合长驻进程日志轮转）
- 新增：
  - `ops/launchd/install_core.sh`：一键安装核心 agents（并自动替换 plist 里旧的绝对路径前缀）
  - `ops/launchd/prune_optional.sh`：一键卸载并禁用 one-shot agents（防止重启后误跑）

---

## 10) 其它修复/增强
- `/api/status` 增强：增加 jobs 汇总、pipeline 配置快照、recent_skipped
- 前端：Admin 页面可滚动（全站 `body overflow hidden` 下的兼容修复）
- 去掉 `@vercel/analytics` 噪声，并对 `/_vercel/insights/*` 增加 silence route

---

## 11) 公网入口（Cloudflare Tunnel，无 VPS）
- 在 Mac mini 上配置 Cloudflare Tunnel（cloudflared）把本机 `127.0.0.1:8000` 暴露为公网 HTTPS：`https://papertok.app-so.com`
- 主站 `/` 保持公开访问

---

## 12) Cloudflare Access（Zero Trust）保护 Admin UI + Admin API
- 创建可重用策略（仅允许指定邮箱）
- 自托管应用拆分为两条路径并绑定同一策略：
  - `papertok.app-so.com/admin*`
  - `papertok.app-so.com/api/admin*`
- 叠加后端 `X-Admin-Token`（`PAPERTOK_ADMIN_TOKEN`）作为第二道门

---

## 13) 移动端/公网同源加载修复（前端）
- 统一前端 API_BASE 策略：生产/隧道环境默认使用 `window.location.origin`；仅在 localhost 开发时 fallback 到 `:8000`
- 移除“等待图片预加载完成才渲染”的阻塞逻辑，避免移动网络下单张图片卡住导致一直 Loading

---

## 14) S0 安全收口（信息泄露治理 + public/admin status 分离）
- `GET /api/papers/{id}` 不再返回本机绝对路径字段（如 `raw_text_path`）
- `GET /api/status` 改为“公共摘要”（不包含 `/Users/...`、`log_path`、jobs 列表等敏感运维信息）
- 新增：
  - `GET /api/public/status`（公共摘要别名）
  - `GET /api/admin/status`（管理版详细 status，需 `X-Admin-Token` 且由 Cloudflare Access 保护）
- 新增 `ops/security_smoke.sh`：对 Access gating + token enforcement + 信息泄露关键字进行回归检测

---

## 15) iOS/Android App（Capacitor，Internal Build）工程化落地
- 在 `frontend/wikitok/frontend/` 初始化 Capacitor，并提交原生工程目录：
  - `ios/`（SPM，无需 CocoaPods）
  - `android/`
- 新增 Capacitor 构建模式：`vite build --mode capacitor`
  - 使用 `.env.capacitor` 注入 `VITE_API_BASE=https://papertok.app-so.com`（阶段 1：仅公网）
  - `mode=capacitor` 时禁用 PWA（避免 WebView 下 Service Worker 缓存干扰）
- 新增脚本：
  - `npm run cap:sync:ios` / `cap:open:ios`
  - `npm run cap:sync:android` / `cap:open:android`
- 前端实现 `API_BASE` 单点真理：`src/lib/apiBase.ts`，避免 WebView 环境 base 计算分叉
- 新增 runbook：`docs/APP_INTERNAL_RUNBOOK.md`
