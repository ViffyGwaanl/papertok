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
- 在 Mac mini 上配置 Cloudflare Tunnel（cloudflared）把本机 `127.0.0.1:8000` 暴露为公网 HTTPS：`https://papertok.ai`（主域 / canonical）
- 域名规范化：`https://papertok.net/*` **301 永久重定向**到 `https://papertok.ai/$1`（保留 path + query）
- 主站 `/` 保持公开访问

---

## 12) Cloudflare Access（Zero Trust）保护 Admin UI + Admin API
- 创建可重用策略（仅允许指定邮箱）
- 自托管应用拆分为两条路径并绑定同一策略：
  - `papertok.ai/admin*`
  - `papertok.ai/api/admin*`
- 由于 `papertok.net/*` 已 301 到 `papertok.ai`，通常**无需**再为 `papertok.net` 单独维护 Access Applications（除非你刻意保留别名域直连）。
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
  - 使用 `.env.capacitor` 注入 `VITE_API_BASE=https://papertok.ai`（阶段 1：仅公网；不要再设成 `https://papertok.net`，否则会多一次 301）
  - `mode=capacitor` 时禁用 PWA（避免 WebView 下 Service Worker 缓存干扰）
- 新增脚本：
  - `npm run cap:sync:ios` / `cap:open:ios`
  - `npm run cap:sync:android` / `cap:open:android`
- 前端实现 `API_BASE` 单点真理：`src/lib/apiBase.ts`，避免 WebView 环境 base 计算分叉
- 新增 runbook：`docs/APP_INTERNAL_RUNBOOK.md`

---

## 16) 真机验收：iOS/Android 均已在本地成功安装运行
- iOS：本地 Xcode（Personal Team）成功 Run 并安装到 iPhone（internal build）
- Android：本地 Android Studio 成功导入 Gradle 工程、安装并运行到真机
- 经验记录（写入 runbook，便于复现/交接）：
  - Android Studio 首次导入会提示安装 SDK（API Platform/Build-Tools/Platform-Tools）
  - `adb: command not found` 通常是 Platform-Tools 未装或 PATH 未配置

---

## 17) Android APK 分发（Release 签名 + GitHub Releases）
- 增加 release 签名配置模板（读取 `~/.gradle/gradle.properties` 或同名环境变量；仓库不落密钥）
- 增加一键脚本：`ops/build_android_release_apk.sh`（产出 `exports/android/*.apk` + `.sha256`）
- 增加发布文档：`docs/ANDROID_APK_RELEASE.md`（包含 GitHub Releases 分发流程）

---

## 18) Feed 完成稿 gating（讲解 + 图注 + 生成图）
- DB config 新增：`feed_require_image_captions`、`feed_require_generated_images`
- `/api/papers/random` 默认只展示“讲解 + 图注 + 生成图”都齐的论文卡片
- Admin 页面支持这两个开关（手机端可配置）

## 19) Scheme B：Release-based Deployment（releases + current）
- 新增 release 构建与切换脚本：
  - `ops/release/prepare_shared.sh`
  - `ops/release/build_release.sh`
  - `ops/release/switch_current.sh`
- 新增 release-mode LaunchAgents 模板与安装脚本：
  - `ops/launchd/release/*.plist`
  - `ops/launchd/install_release_current.sh`
- 新增部署文档：`docs/RELEASE_DEPLOYMENT.md`

## 20) Prod shared 去 symlink 化（降低 workspace 误操作风险）
- `~/papertok-deploy/shared/.env` 迁移为真实文件（路径变量改到 deploy/shared/data）
- `~/papertok-deploy/shared/data` 迁移为真实目录（workspace 原路径保留为指向 deploy 的 symlink 兼容层）
- 受磁盘空间影响，`shared/venv` 暂时保留为 symlink（后续再做完整隔离）

## 21) Dev 环境：全流程回归（冻结论文数据集）
- 建议目录：`~/papertok-dev/repo` + `~/papertok-dev/shared/{.env,data,venv}`
- 冻结数据集：`HF_TOP_N=0` + `DOWNLOAD_PDF=0`（不新增论文）
- dev server 绑定本地端口（示例：`127.0.0.1:8001`）
- 提供 dev 回归脚本：`ops/dev/run_full_pipeline_existing.sh`
- Python 版本建议：3.13（macOS 上 3.14 可能触发 pydantic-core/PyO3 构建失败）

## 22) ZH/EN 双语全链路（Schema + API + Pipeline + UI）
- DB schema：
  - `papers` 增加英文字段：`one_liner_en`、`content_explain_en`、`image_captions_en_json`
  - `paper_images` 增加 `lang` 列（同一篇论文可同时有 `zh/en` 两套生成图）
- API：
  - `/api/papers/random` 与 `/api/papers/{id}` 增加 `lang=zh|en|both`
  - Feed gating 语言化（方案 A）：
    - `lang=en` 时只要求英文链路齐全（`*_en` + `PaperImage(lang='en')`）
    - `lang=zh` 时只要求中文链路齐全
- Pipeline：
  - one-liner / explain / captions / images 全部按 `lang` 生成并写回对应字段
  - 生图产物路径按语言分目录：`/static/gen_glm/<external_id>/<lang>/...`

## 23) 任务队列（Jobs）双语化 + 并发控制
- 新增 scoped/regen 任务（均支持指定 day/lang/external_ids）：
  - `one_liner_scoped` / `one_liner_regen_scoped`
  - `content_analysis_scoped` / `content_analysis_regen_scoped`
  - `image_caption_scoped` / `image_caption_regen_scoped`
  - `paper_images_scoped` / `paper_images_regen_scoped`
- 图注任务增加并发参数：`IMAGE_CAPTION_CONCURRENCY`（避免 VLM 429，并提升吞吐）

## 24) 前端：内容语言切换 + UI 文案 i18n（Web）
- 右上角增加 `中文/EN` 内容切换（持久化到 `localStorage('papertok:contentLang')`）
- 修复语言切换“必须刷新才生效”的竞态（丢弃旧语言 in-flight 请求结果）
- 详情弹窗按钮/标签（讲解/原文/图片/页面/关闭/图注/加载中…）随语言切换

## 25) 线上回归（latest day 2026-02-10）
- 英文链路补齐：`one_liner_en`、`content_explain_en`、`image_captions_en_json`、英文生成图（GLM）
- 英文生成图完成：10 篇 × 3 张 = 30 张（`PAPER_IMAGES_GENERATE_ONLY_DISPLAY=1` 节省成本）

## 26) 回填编排：最近 7 天双语补齐 + “完成验收”监控
- 增加回填入队脚本：`ops/backfill/run_bilingual_backfill_last7_days.sh`
- 增加按天验收监控脚本：`ops/backfill/monitor_day_completion.py`
  - 严格 8 指标：zh/en one-liner、zh/en explain、zh/en caption、glm/seedream images total
  - 仅当某天“达标”才输出报告，并用 state file 避免重复通知

## 27) Android 发布链路打通（GitHub Releases）
- 已通过 `gh release create` 发布 internal build APK（含 `.sha256`）
- 记录了 macOS iCloud Drive/File Provider 目录的限制：
  - 在 `~/Library/Mobile Documents/...`（例如“互传”）下可能出现 `Resource deadlock avoided`，导致后台进程无法读取/上传
  - 解决：先将 APK/sha256 拷贝到本地非 iCloud 目录（如 `~/Downloads/` 或 `exports/android/`）再发布

## 28) 移动端语言切换竞态修复（App 友好）
- 修复“切到 EN 后外层卡片 one-liner 仍显示中文，但弹窗/按钮已是英文”的问题
- 技术要点：语言切换时原子清空 feed + 按 generation 管控 in-flight 请求与 loading 状态 + 离线缓存 key 按语言隔离
