# PaperTok Handbook（工程化说明书）

> 版本：2026-02-07（持续更新；涵盖：Cloudflare Tunnel/Access 公网入口、移动端同源加载修复等）

## 1) 总体概览

PaperTok 是一个本地部署的“论文版 TikTok/WikiTok”应用：
- 每天抓取 Hugging Face Daily Papers **当天 Top10**
- 下载 arXiv PDF
- 使用 **MinerU CLI** 本地解析 PDF → markdown + 抽图
- 用 LLM 生成中文教学式讲解（`content_explain_cn`）
- 用 VLM 给抽取图片生成中文图注（缓存到 DB）
- 同时用两家图像模型生成“实体手工剪贴簿/杂志拼贴”风格竖屏图：**Seedream + GLM-Image**
- 后端 FastAPI 提供 API，并托管前端 `dist/`，手机端竖滑浏览

### 1.1 设计目标
- **本地优先**：Mac mini 单机长期跑。
- **单服务稳定**：后端同源托管前端，避免跨域/localhost 黑屏。
- **长任务不在请求路径**：所有重活走后台脚本 / Jobs 队列。
- **No Fake Data**：MinerU/讲解生成不了就跳过；Feed 默认不展示未完成讲解的论文。
- **可运维、可观察**：Admin 配置/入队/查看日志；`/api/status` + `paper_events`。

### 1.2 非目标（当前阶段不做）
- 分布式队列、K8s、复杂权限系统
- 在线多用户账号体系
- 将 MinerU 改为远程服务（目前固定为本机 CLI）

---

## 2) 快速开始

### 2.1 前置条件
- macOS（当前用 launchd 做常驻）
- Python（建议 3.13）
- Node/npm（前端 build）
- MinerU CLI 可用（安装见 `backend/requirements.mineru.txt`）
- 可选：`qpdf`（用于 PDFium “data format error” 的保守修复）

### 2.2 一次性初始化
```bash
cd papertok
cp .env.example .env  # 注意：不要提交 .env

# backend venv
cd backend
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# MinerU heavy deps 如需要：pip install -r requirements.mineru.txt

# frontend build
cd ../frontend/wikitok/frontend
npm install
npm run build
```

### 2.3 启动（推荐：launchd 核心 4 个）
```bash
cd papertok
bash ops/launchd/install_core.sh

# 查看
launchctl list | rg com\.papertok
```

访问：
- 前端：`http://127.0.0.1:8000/`
- Admin：`http://127.0.0.1:8000/admin`
- 健康检查：`GET /healthz`

### 2.4 运行一次完整流水线（手动）
```bash
cd papertok
bash ops/run_daily.sh
```

---

## 3) 架构与关键设计决策

### 3.1 单服务托管前端（同源）
- FastAPI 在 `app/main.py` 中将 Vite build 输出目录（`FRONTEND_DIST_DIR`）mount 到 `/`
- SPA 深链 `/admin` / `/admin/*` 有专门 fallback 到 `index.html`

优点：
- 避免 LAN + localhost 混用导致的移动端白屏
- 避免 CORS、端口不一致等问题

### 3.2 长任务后台化：Jobs 队列 + Worker
- 所有“可能分钟级”的任务都走 `jobs` 表 + `job_worker`
- Admin 页面提供入队、查看最近 jobs、tail job log
- Worker 使用 launchd 每 60s poll 一次队列（也可 Admin 里 Kick）

### 3.3 两套生图供应商并存
- DB `paper_images` 表存两套 provider（seedream/glm）生成结果
- Feed 卡片显示哪一套由 DB 配置 `paper_images_display_provider` 决定（seedream | glm | auto）

### 3.4 No Fake Data / Feed 默认只显示已讲解
- 默认配置 `feed_require_explain=True`
- `/api/papers/random` 会过滤掉没有 `raw_text_path` 或 `content_explain_cn` 的论文

### 3.5 PDF 修复策略（保守）
- **原始 PDF 不动**
- MinerU 失败时才尝试把 PDF 修到缓存目录 `data/raw/pdfs_repaired/`，然后用修复版重跑

---

## 4) 数据目录与数据模型

### 4.1 数据目录（papertok/data）
- `data/db/papertok.sqlite`：SQLite DB
- `data/raw/pdfs/`：下载的原始 PDF（静态挂载 `/static/pdfs`）
- `data/raw/pdfs_repaired/`：修复缓存 PDF（仅在 MinerU 失败后生成）
- `data/mineru/`：MinerU 输出（markdown + images，静态挂载 `/static/mineru`）
- `data/gen_images/`：Seedream 生成图（挂载 `/static/gen`）
- `data/gen_images_glm/`：GLM 生成图（挂载 `/static/gen_glm`）
- `data/logs/`：所有 launchd/job 的日志

### 4.2 主要数据表（概念级）
- `papers`：论文主表（含 day、pdf_path、raw_text_path、content_explain_cn、image_captions_json…）
- `paper_images`：生成图/抽图（这里主要用 generated + provider + order_idx）
- `paper_events`：可观测性事件（stage: pdf/mineru/pdf_repair/explain/caption/paper_images；status: started/success/failed/skipped）
- `jobs`：后台任务队列（queued/running/success/failed）
- `app_settings`：DB 配置（Admin 可改）

---

## 5) 配置体系：env vs DB config

### 5.1 原则
- **机密/路径/运行环境**：只放 `.env`（不提交，gitignored）
- **运行时策略（可在 Admin 调整）**：放 DB config（`app_settings`）

### 5.2 `.env`（单一事实源）
- 后端启动、ops 脚本、launchd 统一读取 `papertok/.env`
- 参考模板：`papertok/.env.example`

### 5.3 DB Config（Admin 可改）
`GET/PUT /api/admin/config` 当前可调整：
- `feed_require_explain`：Feed 是否只展示已讲解
- `paper_images_display_provider`：seedream|glm|auto
- `image_caption_context_chars / strategy / occurrences`：图注上下文策略

---

## 6) API 说明

### 6.1 健康检查
- `GET /healthz` → `{ok: true}`

### 6.2 Feed / 论文
- `GET /api/papers/random?limit=20&day=latest|YYYY-MM-DD|all`
  - 默认：按 DB config 过滤未讲解论文（可关闭）
- `GET /api/papers/{id}`
  - 详情包含 `content_explain_cn`、`raw_markdown_url`、抽取图片、图注、两家生成图

### 6.3 状态与运维观测
- **Public（可公开）**
  - `GET /api/status`（公共摘要；不含本机路径/日志路径/运维细节）
  - `GET /api/public/status`（同上，显式命名的别名）

- **Admin（仅管理面）**
  - `GET /api/admin/status`（完整运维视图；需要 `X-Admin-Token` 且建议由 Cloudflare Access 保护）

公共摘要包含：覆盖率、聚合计数、pipeline 开关快照、按 provider 的生图统计等；
管理视图额外包含：recent_failed 列表、log_path、running jobs 等敏感运维信息。

### 6.4 Admin（需要可选 token）
- `GET/PUT /api/admin/config`
- `GET /api/admin/jobs`：列 job + 支持的 job_type
- `POST /api/admin/jobs/{job_type}`：入队
- `GET /api/admin/jobs/{id}`：job 详情
- `GET /api/admin/jobs/{id}/log?tail_lines=200`：tail 日志
- `POST /api/admin/jobs/worker/kick`：触发 worker 立即 poll（macOS）
- `GET /api/admin/jobs/worker_logs/meta`：worker out/err 文件大小
- `POST /api/admin/jobs/worker_logs/truncate`：清空 worker out/err

---

## 7) 流水线与可观测性

### 7.1 主流水线（`backend/scripts/daily_run.py`）
按阶段：
1) ingest HF daily（只取当天 Top10；历史累积）
2) 下载 PDF
3) MinerU 解析
   - 失败后可选触发 pdf_repair（qpdf/mutool/gs）→ 使用缓存副本重试
4) explain：生成 `content_explain_cn`
5) caption：抽图图注（带 markdown 上下文窗口）
6) paper_images：两家各生成 N 张（默认 3）

### 7.2 事件体系（paper_events）
- 每个 stage 会写 started/success/failed
- 对“没有跑”的情况：
  - 在 per-paper retry（Admin）中，如果前置条件不足会写 `skipped`
  - 提供一次性 backfill job（见下一章）将“现有 DB 状态”补成事件，打开面板即可读

---

## 8) Admin / Jobs / Worker 运维

### 8.1 Jobs 设计
- DB `jobs` 表记录任务：queued → running → success/failed
- 每个 job 对应一个独立日志文件：`data/logs/job_<id>_<type>.log`

### 8.2 已支持的 job_type（Admin 页面可直接入队）
- `image_caption_scoped`：补齐缺失图注（按 scope）
- `image_caption_regen_scoped`：wipe+重生成图注（按 scope）
- `paper_images_glm_backfill`：补齐所有论文的 GLM 生图
- `paper_events_backfill`：为当前 DB 状态补齐 paper_events 标记（skipped/success）
- `paper_retry_stage`：对某篇论文重试某个 stage（pdf/mineru/explain/caption/paper_images）

### 8.3 Worker 行为
- launchd `com.papertok.job_worker` 每 60s 运行一次 worker（poll N 个 job）
- Admin 的 “Kick worker now” 会触发立即执行（**非打断式**，避免 job stuck）

---

## 9) launchd 与日志轮转（macOS）

### 9.1 核心长期任务（只建议保留这 4 个）
- `com.papertok.server`
- `com.papertok.job_worker`
- `com.papertok.daily`
- `com.papertok.logrotate`

一键安装/更新：
```bash
bash ops/launchd/install_core.sh
```

### 9.2 一次性重任务的风险控制
历史上仓库里曾存在多个 one-shot plist（caption/paper_images/regen/backfill 等）。
工程上建议：
- **不要长期 load**（否则重启/登录可能自动跑重活）
- 统一改为 Admin → Jobs enqueue

如果你以前 load 过很多 one-shot：
```bash
bash ops/launchd/prune_optional.sh
```

### 9.3 日志轮转策略
- `com.papertok.logrotate` 每天跑一次 `ops/run_logrotate.sh`
- 对 `data/logs/*.log` 超过阈值的文件进行轮转
- 轮转方式：**copy + truncate**（不破坏长驻进程的 fd）

---

## 10) 安全边界（LAN 安全）

### 10.1 IP Allowlist（默认开启）
- Middleware：`ClientIPAllowlistMiddleware`
- 默认允许：localhost + 私网网段（10/172.16/192.168 等）
- 关闭 allowlist：`PAPERTOK_ALLOWED_CIDRS=*`

### 10.2 可选 Basic Auth
- Middleware：`BasicAuthMiddleware`
- 适合你在局域网临时暴露给更多设备时加一道门

### 10.3 Admin Token
- 若设置 `PAPERTOK_ADMIN_TOKEN`，则 `/api/admin/*` 与 `/api/admin/jobs/*` 必须带 `X-Admin-Token`

### 10.4 公网发布的推荐安全组合（Cloudflare Tunnel + Access）
当你用 Cloudflare Tunnel 把服务暴露到公网时，推荐采用“分层防护”（Defense in Depth）：

1) **主站公开 / 只保护 Admin**（推荐的默认姿势）
- `.env`：
  - `PAPERTOK_ALLOWED_CIDRS=*`（不限制主站 IP）
  - `PAPERTOK_ADMIN_TOKEN=...`（强制 Admin API header）
- Cloudflare Access：
  - 保护 `papertok.ai/admin*`（Admin UI）
  - 保护 `papertok.ai/api/admin*`（Admin API）
  - （可选）`papertok.net` 作为别名时也做同样保护，或直接 301 到 `papertok.ai`
  - 策略仅允许你的邮箱（如 `qq983929606@gmail.com`）

2) **继续启用 IP allowlist（更严格）**
- 若你仍希望用 IP allowlist（例如只允许自己公司的出口 IP），并且前面有 Cloudflare 代理：
  - 设置 `PAPERTOK_TRUST_X_FORWARDED_FOR=1`
  - 并把 `PAPERTOK_ALLOWED_CIDRS` 设为你想允许的公网/内网网段

> 说明：Cloudflare Access 负责“谁能进来”，`X-Admin-Token` 负责“即使进来了也要再验一次”。两者叠加很稳。

---

## 11) 故障排查 Runbook

### 11.1 Feed 没数据 / 只看到很少
- 默认 `feed_require_explain=True`：未讲解论文会被过滤
- 去 `/admin` 里把该开关关掉验证是否是过滤导致

### 11.2 MinerU 报错：PDFium Data format error
现象：
- `pypdfium2 ... PdfiumError: Failed to load document (PDFium: Data format error)`

处理：
- 确认已安装 `qpdf`（推荐）：`brew install qpdf`
- 打开 `.env`：确保 `MINERU_REPAIR_ON_FAIL=1` 且 `MINERU_REPAIR_TOOL=auto|qpdf`
- 通过 Admin → `paper_retry_stage` 重试 `mineru`（会触发 repair-on-fail）

### 11.3 页面更新不生效（PWA / Service Worker 缓存）
现象：你明明已经更新了代码，但手机端仍在用旧 JS/CSS，于是出现“Loading 转圈/图片不出/弹窗不出”等。

处理顺序（从轻到重）：
1) 用无痕窗口打开（最常用）：`/` 或 `/admin`
2) URL 加版本号强制刷新：`https://papertok.ai/?v=3`（随便换个数字即可；别名用 `https://papertok.net/?v=3`）
3) iOS：设置 → Safari → 高级 → 网站数据 → 删除 `papertok.ai`（如使用别名，也删除 `papertok.net`）
4) 如果是“添加到主屏幕”的 PWA：删除桌面图标后重新添加

### 11.4 worker job 卡住 running
- 当前做法：避免 kickstart -k 杀进程；worker 内也有 stale 处理（如果你再遇到可继续增强）

### 11.5 S0 安全回归检查（上线/改动后必跑）
运行：
```bash
cd papertok
./ops/security_smoke.sh
```
它会验证：
- Cloudflare Access 仍然保护 `/admin*` 与 `/api/admin*`
- 本机直连 `/api/admin/*` 没有 `X-Admin-Token` 必须 401
- 公网 `/api/status` 与 `/api/papers/{id}` 不泄露 `/Users/...`、`log_path` 等敏感信息

---

# 附录：在哪里看“真实进度”

- `/api/status`：覆盖率、近期失败、jobs 状态
- `data/logs/`：launchd 与 job 日志
- `/admin`：入队/重试/查看日志
