# PaperTok (MVP)

目标：本地部署 PaperTok —— 每天抓取 Hugging Face Daily Papers **当天 Top10**，离线跑完整流水线（PDF → MinerU → 讲解 → 图注 → Seedream+GLM 杂志拼贴图 → one-liner），并用 WikiTok 风格的无限竖滑来浏览。

## 文档（推荐先读）
- 总文档/运维手册：`papertok/docs/Handbook.md`
- 项目历史（我们已经做过什么）：`papertok/docs/HISTORY.md`
- Roadmap（未来计划）：`papertok/docs/ROADMAP.md`

## 当前已经做了什么（现状）
- ✅ FastAPI + SQLite（SQLModel）后端
- ✅ 同源单服务：后端托管前端 `dist/`，避免前后端分开导致的黑屏/跨域/localhost 问题
- ✅ 公网入口（无 VPS）：Cloudflare Tunnel → `https://papertok.ai/`（主域 / canonical）
- ✅ 域名规范化：`https://papertok.net/*` **301 永久重定向**到 `https://papertok.ai/$1`（保留 path + query）
- ✅ Zero Trust：Cloudflare Access 保护 `/admin*` 与 `/api/admin*`（仅允许指定邮箱）
- ✅ API：
  - `GET /healthz`
  - `GET /api/papers/random?limit=20`（默认全历史；支持 `day=latest` 或 `day=YYYY-MM-DD`）
  - `GET /api/papers/{id}`（弹窗详情：讲解/原文 MD/图片+图注/PDF/生成图）
  - `GET /api/status`（公共摘要：状态/覆盖率/聚合计数；不含本机路径/日志路径等敏感运维信息）
  - `GET /api/public/status`（同上，显式别名）
  - `GET /api/admin/status`（管理版详细状态：需要 `X-Admin-Token`，且建议由 Cloudflare Access 保护）
  - `GET /api/admin/config` + `PUT /api/admin/config`（DB 配置；配合 `/admin` 页面）
- ✅ Pipeline（脚本 `backend/scripts/daily_run.py`）：
  - HF Daily 当天 Top10 入库（只处理 Top10，但历史会累积保留）
  - arXiv PDF 下载（本地挂载 `/static/pdfs`）
  - MinerU：PDF → markdown + extracted images（挂载 `/static/mineru`）
  - 讲解：从 MinerU markdown 生成中文教学式讲解（`content_explain_cn`）
  - 图片图注：对 MinerU 抽取图片做 VLM caption（缓存到 `image_captions_json`）
  - 杂志拼贴图：Seedream / GLM-Image 生成 3 张/篇（`paper_images` 表 + `/static/gen` & `/static/gen_glm`），首页卡片支持横向轮播
- ✅ PWA 的 Service Worker 已修：打开 `/static/*` 不会被错误 fallback 到首页
- ✅ Capacitor 构建模式（`vite build --mode capacitor`）默认禁用 PWA/SW，避免 WebView 缓存干扰
- ✅ 移动端/公网同源加载修复：前端默认使用 `window.location.origin` 访问 API（不再硬编码 `:8000`）
- ✅ iOS/Android（Internal Build）骨架已落地：Capacitor 工程（`frontend/wikitok/frontend/ios` + `android`）已提交；阶段 1 仅使用公网 `https://papertok.ai`（主域 / canonical；避免 `papertok.net` 额外 301 跳转）（见 `docs/APP_INTERNAL_RUNBOOK.md`）
- ✅ 前端 `API_BASE` 单点真理：`frontend/wikitok/frontend/src/lib/apiBase.ts`
- ✅ 移除弹窗“PDF(本地)”入口（保留 arXiv PDF）

## 后续计划做什么（Roadmap）
- [x] 每日任务（模式 C）已接入 launchd（见 `papertok/ops/launchd/INSTALL.md`）
- [x] 增加日志轮转（`daily/server` log 变大后会需要；见 `ops/launchd/com.papertok.logrotate.plist`）
- [x] 安全收口（默认启用 IP 白名单：仅允许私网网段/localhost；可选 Basic Auth；见 `.env.example`）
- [ ] 前端手势/轮播在更多手机浏览器上做一致性验证
- [x] 域名规范化：`papertok.net/*` → `papertok.ai/$1`（301，保留 query）
- [x] 可观测性：`/api/status` 已补齐缺失字段计数、按 provider 的生图覆盖、最近失败摘要

## 组件
- `backend/` FastAPI：提供 `/api/papers/random` 等接口
- `backend/scripts/`：每日任务（抓取 → 入库 → 生成摘要）
- `frontend/`：后续放 fork 的 wikitok（把数据源换成 backend API）
- `data/`：本地数据目录（SQLite、原始文件、mineru 输出、缩略图等）

## 快速开始（单服务：后端 + 托管前端）

1) 构建前端（生成 `frontend/wikitok/frontend/dist/`）
```bash
cd frontend/wikitok/frontend
npm install
npm run build
```

2) 启动后端（会自动托管 dist）
```bash
cd backend
# 建议用 Python 3.13（macOS 上 python3.14 会导致 pydantic-core 无法安装）
/opt/homebrew/bin/python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# unified env lives at papertok/.env
cd ..
cp .env.example .env
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开：`http://127.0.0.1:8000/`

后台（Admin）：`http://127.0.0.1:8000/admin`

## 局域网访问（手机/其他电脑）

后端默认会监听 `0.0.0.0:8000`（通过 launchd 的 `com.papertok.server`）。

1) 查本机局域网 IP（macOS）
```bash
ipconfig getifaddr en0  # 有线
ipconfig getifaddr en1  # Wi‑Fi
```

2) 在同一 Wi‑Fi 下用手机打开：
`http://<LAN-IP>:8000/`

> 如果打不开：
> - 确认手机和 Mac 在同一个局域网、路由器没有“AP/客户端隔离”
> - macOS 防火墙可能会拦截 Python/uvicorn 的入站连接（系统弹窗允许即可）
> - 端口被占用时可用：`launchctl kickstart -k gui/$(id -u)/com.papertok.server`
> - 如果页面一直 Loading/图片不出：可能是 PWA/Service Worker 缓存，试试无痕窗口或 URL 加 `?v=3` 强制刷新


> 说明：如果 dist 不存在，后端仍可用（API 正常），但 `/` 会提示先 build 前端。

## 快速开始（开发模式：前后端分开跑）
- 后端：同上（8000）
- 前端：`cd frontend/wikitok/frontend && npm run dev -- --host 127.0.0.1 --port 5173`

> 说明：前端默认会在“localhost dev server”场景下把 API 指到 `http://localhost:8000`；在生产/隧道场景下默认走同源 `window.location.origin`。

运行一次每日任务（手动，模式 C）：
```bash
/Users/gwaanl/.openclaw/workspace/papertok/ops/run_daily.sh
```

安装 launchd（每日 09:00 自动跑）：
见：`papertok/ops/launchd/INSTALL.md`

API：
- `GET http://localhost:8000/healthz`
- `GET http://localhost:8000/api/papers/random?limit=20`

> 注意：不要把任何 API Key 写进仓库；全部放 `.env`。
