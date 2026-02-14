# PaperTok 项目历史（已完成工作清单）

> 目的：把“我们之前做过的所有事”按可审计的方式写清楚，便于回溯与交接。

## 0) 里程碑概览

- M0：端到端 MVP 跑通（HF Top10 → PDF → MinerU → explain → captions → images → FE）
- M1：Admin Config（DB-backed）
- M2：Jobs 队列 + Worker（后台长任务）
- M3：Alembic migrations（可演进 schema）
- M4：paper_events（失败闭环与可观测性）
- P1 Ops：launchd 收口、日志轮转、路径可迁移性
- Bilingual：ZH/EN 全链路（Schema + API + Pipeline + UI）

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

已支持 job（节选）：
- `image_caption_scoped` / `image_caption_regen_scoped`
- `paper_images_scoped` / `paper_images_regen_scoped`
- `content_analysis_scoped` / `content_analysis_regen_scoped`
- `one_liner_scoped` / `one_liner_regen_scoped`
- `paper_retry_stage`
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

---

## 10) 公网入口（Cloudflare Tunnel，无 VPS）
- 在 Mac mini 上配置 Cloudflare Tunnel（cloudflared）把本机 `127.0.0.1:8000` 暴露为公网 HTTPS：`https://papertok.ai`（主域 / canonical）
- 域名规范化：`https://papertok.net/*` **301 永久重定向**到 `https://papertok.ai/$1`（保留 path + query）
- 主站 `/` 保持公开访问

---

## 11) Cloudflare Access（Zero Trust）保护 Admin UI + Admin API
- 创建可重用策略（仅允许指定邮箱）
- 自托管应用拆分为两条路径并绑定同一策略：
  - `papertok.ai/admin*`
  - `papertok.ai/api/admin*`
- 叠加后端 `X-Admin-Token`（`PAPERTOK_ADMIN_TOKEN`）作为第二道门

---

## 12) 移动端/公网同源加载修复（前端）
- 统一前端 API_BASE 策略：生产/隧道环境默认使用 `window.location.origin`
- 移除“等待图片预加载完成才渲染”的阻塞逻辑，避免移动网络下单张图片卡住导致一直 Loading

---

## 13) S0 安全收口（信息泄露治理 + public/admin status 分离）
- `GET /api/papers/{id}` 不再返回本机绝对路径字段（如 `raw_text_path`）
- `GET /api/status` 改为“公共摘要”（不包含 `/Users/...`、`log_path`、jobs 列表等敏感运维信息）
- 新增 `GET /api/admin/status`（管理版详细 status，需 `X-Admin-Token` 且由 Cloudflare Access 保护）
- 新增 `ops/security_smoke.sh`：对 Access gating + token enforcement + 信息泄露关键字进行回归检测

---

## 14) iOS/Android App（Capacitor，Internal Build）工程化落地
- 在 `frontend/wikitok/frontend/` 初始化 Capacitor，并提交原生工程目录：`ios/`、`android/`
- 新增 Capacitor 构建模式：`vite build --mode capacitor`（禁用 PWA/SW）
- 新增 runbook：`docs/APP_INTERNAL_RUNBOOK.md`

---

## 15) Android APK 分发（Release 签名 + GitHub Releases）
- 增加 release 签名配置模板（读取 `~/.gradle/gradle.properties` 或同名环境变量；仓库不落密钥）
- 增加一键脚本：`ops/build_android_release_apk.sh`（产出 `exports/android/*.apk` + `.sha256`）
- 增加移动 tag `android-latest`：提供稳定下载链接 `/releases/latest/download/papertok-android-latest.apk`
- 记录 iCloud/互传目录可能导致后台读取失败（`Resource deadlock avoided`）的规避方法

---

## 16) Feed 完成稿 gating（讲解 + 图注 + 生成图）
- DB config 新增：`feed_require_image_captions`、`feed_require_generated_images`
- `/api/papers/random` 默认只展示“讲解 + 图注 + 生成图”都齐的论文卡片

---

## 17) Scheme B：Release-based Deployment（releases + current）
- 新增 release 构建与切换脚本 + release-mode LaunchAgents
- 新增部署文档：`docs/RELEASE_DEPLOYMENT.md`

---

## 18) Prod shared 去 symlink 化（降低 workspace 误操作风险）
- `~/papertok-deploy/shared/.env` 迁移为真实文件
- `~/papertok-deploy/shared/data` 迁移为真实目录
- `~/papertok-deploy/shared/venv` 迁移为真实 venv 目录（Python 3.13 推荐）
- `~/papertok-deploy/current/backend/.venv` 指向 `shared/venv`，prod 不再依赖 workspace venv

---

## 19) Dev 环境：全流程回归（冻结论文数据集）
- 建议目录：`~/papertok-dev/repo` + `~/papertok-dev/shared/{.env,data,venv}`
- dev 回归脚本：`ops/dev/run_full_pipeline_existing.sh`

---

## 20) ZH/EN 双语全链路（Schema + API + Pipeline + UI）
- DB schema：英文字段 + `paper_images.lang`
- API：`lang=zh|en|both`，并采用“按请求语言判断完成稿（Strategy A）”
- Pipeline/Jobs：one-liner/explain/captions/images 全部按 `lang` 生成
- 前端：内容语言切换 + UI i18n；修复语言切换竞态

---

## 21) 双语回填收敛（按天验收）
- 增加按天验收监控：8 指标（zh/en one-liner、zh/en explain、zh/en captions、生成图完整）
- 最近 7 天回填已收敛并达标；队列跑空后再逐步扩大全量回填范围

---

---

_Last updated: 2026-02-14_
