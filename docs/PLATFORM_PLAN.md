# PaperTok 多平台兼容 & 可部署性计划（Server + Windows）

> 目标：在保持当前 Mac mini 本地 MVP 可用的前提下，把 PaperTok 演进成：
> - 可在 **Linux 服务器**稳定部署（含后台 worker、定时任务、日志、权限/安全边界）
> - 可在 **Windows 本地**运行（至少 API + 前端浏览 + Jobs/worker；MinerU 若不支持则提供替代运行方式）
>
> 该计划按软件工程方式拆解：范围/目标、原则、架构调整、里程碑、验收标准、风险与缓解。

---

## 1) 范围与目标

### 1.1 目标平台
- **macOS（现状）**：继续支持（launchd 作为一种部署方式，但不再是唯一方式）
- **Linux Server（优先 Ubuntu 22.04/24.04）**：systemd 或容器化部署
- **Windows 11（本地）**：原生 Python 运行（可选 WSL2/容器作为增强方案）

### 1.2 兼容目标（分层）
- **L0（必须）**：API 服务启动、前端可访问、DB 可用、静态文件可访问
- **L1（必须）**：Jobs 队列 + worker 可跑；Admin 可入队/查看日志
- **L2（期望）**：定时 daily pipeline（每天 Top10）跨平台可用
- **L3（可选）**：服务器生产级部署（TLS/反代/限流/备份/监控/多 worker）

### 1.3 非目标（短期不做）
- 多租户账号体系
- 分布式任务队列（例如 Redis/Celery）作为强依赖
- 大规模并发写入（目前 SQLite 足够；未来可升级 Postgres）

---

## 2) 关键工程原则

1) **运行时不可依赖 launchd**
- launchd/systemd/Windows Service 都应只是“外层运行器”。
- 应提供跨平台统一入口（CLI/模块）来启动 server、worker、daily、logrotate。

2) **路径与数据目录必须可配置、可迁移**
- 所有路径从 `PAPERTOK_ROOT` / `PAPERTOK_DATA_DIR` 动态推导（默认 `root/data`）。
- 禁止硬编码 `/Users/...` 或 macOS-only path。

3) **配置分层**
- `.env`：机密、端点、数据目录、运行参数（不可提交）
- DB config（Admin 可改）：运行策略开关（feed_require_explain、展示 provider…）

4) **日志与轮转由应用层统一管理**
- 不依赖 bash 脚本 + OS 特性。
- 优先使用 Python logging + RotatingFileHandler（跨平台）。

5) **可测试、可回归**
- 引入最小 CI：Linux/Windows/macOS 跑单测、lint、类型检查、（可选）前端 build。

---

## 3) 架构调整（为多平台做的“最小必要改造”）

### 3.1 进程模型（跨平台一致）
建议标准化为 3 个可独立运行的进程：
- `papertok-api`：FastAPI（托管 dist + static mounts）
- `papertok-worker`：jobs worker（轮询 DB 队列、执行 job handlers）
- `papertok-scheduler`（可选）：触发 daily run（跨平台定时）

> 说明：
> - Linux 服务器可用 systemd timers 或 cron 触发 daily；也可用 `papertok-scheduler` 常驻。
> - Windows 可用 Task Scheduler 触发 daily；或常驻 scheduler。

### 3.2 引入统一 CLI（替代 bash ops 脚本）
新增 `papertok/backend/scripts/papertokctl.py`（建议用 Typer/Click），提供：
- `papertokctl serve`（启动 API）
- `papertokctl worker --max-jobs N`（跑一轮 worker）
- `papertokctl daily`（跑 daily pipeline）
- `papertokctl logrotate`（轮转日志）
- `papertokctl doctor`（配置/依赖自检：MinerU/qpdf/keys/模型端点可达等）

这样：
- macOS：launchd 仅负责调用 `papertokctl ...`
- Linux：systemd 仅负责调用 `papertokctl ...`
- Windows：PowerShell/任务计划 仅负责调用 `papertokctl ...`

### 3.3 数据目录与静态文件统一
将所有默认路径统一为：
- `PAPERTOK_DATA_DIR` 默认：`<repo>/data`
- 其下：`db/ raw/ mineru/ gen_images/ logs/ ...`

并在 `Settings` 中只保留“可覆盖的逻辑路径”，例如：
- `DB_URL` 默认指向 `${PAPERTOK_DATA_DIR}/db/papertok.sqlite`
- `PAPERS_PDF_DIR` 默认 `${PAPERTOK_DATA_DIR}/raw/pdfs`
- `MINERU_OUT_ROOT` 默认 `${PAPERTOK_DATA_DIR}/mineru`
- `PAPER_GEN_IMAGES_DIR` / `PAPER_GEN_IMAGES_GLM_DIR`
- `PAPERTOK_LOG_DIR` 默认 `${PAPERTOK_DATA_DIR}/logs`

### 3.4 平台相关依赖处理策略
- **MinerU**：需要验证 Windows 是否原生可用。
  - 若可用：直接支持。
  - 若不可用：提供两种 fallback：
    1) Windows + WSL2 运行 MinerU（API/worker 仍可 Windows 原生跑）
    2) Server 侧容器化 MinerU（worker 在 Linux 跑 MinerU stage）
- **qpdf**：
  - macOS：brew
  - Linux：apt
  - Windows：优先用 `qpdf` 的 Windows 发行版或用替代工具（mutool/gs），并在 `doctor` 中给出明确安装指引。

---

## 4) 里程碑与工作分解（WBS）

### Phase 0 — 现状审计（0.5 天）
**交付物**：`docs/PORTABILITY_AUDIT.md`
- 扫描并列出：
  - 所有硬编码路径
  - macOS-only 行为（launchctl、stat -f、sed 语法差异）
  - 外部依赖（qpdf、mineru、opencv 等）

**验收**：明确“阻塞 Windows/Linux 的点”列表。

### Phase 1 — 路径/配置可迁移（1-2 天）
**任务**：
- 引入 `PAPERTOK_DATA_DIR`（或更强：`PAPERTOK_ROOT` + data dir）
- `Settings` 默认值全部基于 repo root / data dir 推导
- `.env.example` 去掉绝对路径示例，改成 `<papertok>/data/...` 注释或相对默认

**验收**：
- 在任意目录 clone 后，按 README 可以启动 API（不需要改源码路径）。

### Phase 2 — 统一 CLI 取代 ops bash（2-4 天）
**任务**：
- 新增 `papertokctl` CLI（serve/worker/daily/logrotate/doctor）
- 现有 launchd/systemd/windows 任务仅做薄封装（调用 CLI）
- 将 logrotate 逻辑搬到 Python（RotatingFileHandler 或应用内轮转）

**验收**：
- macOS 上可完全不用 `ops/run_*.sh` 也能跑全套。

### Phase 3 — Linux Server 部署方案（2-5 天）
两条路径择一（建议都做，先做 A）：

A) **systemd 方案（推荐先做）**
- `papertok.service`（api）
- `papertok-worker.service` + `papertok-worker.timer` 或 `Restart=always`
- `papertok-daily.timer`
- `papertok-logrotate.timer`（或应用内轮转后删除这项）

B) **Docker/Compose（可选）**
- `Dockerfile`（multi-stage：backend + frontend build）
- `docker-compose.yml`（api + worker + 可选 nginx）

**验收**：
- 在一台干净 Ubuntu VM 上，按文档可启动并通过手机访问。

### Phase 4 — Windows 本地支持（2-5 天）
**任务**：
- PowerShell 脚本（可选）或直接文档化：
  - 创建 venv、安装依赖、build 前端、启动 API
  - worker 的运行方式（循环/Task Scheduler）
- 路径分隔符与文件权限检查（pathlib 全覆盖）
- MinerU Windows 可行性验证与 fallback 文档（WSL2/remote）

**验收**：
- Windows 上可打开 `/` 和 `/admin`，可入队 jobs 并成功执行至少 1 类（例如 `paper_events_backfill`、`image_caption_scoped`）。

### Phase 5 — CI / 质量门禁（1-2 天）
**任务**：
- GitHub Actions：matrix（ubuntu-latest / windows-latest / macos-latest）
  - 后端：`python -m py_compile` + unit tests（至少对关键 util）
  - 前端：`npm ci && npm run build`（可选）

**验收**：PR 合并前自动检查通过。

---

## 5) 验收标准（Definition of Done）

### Server DoD
- [ ] API + Admin 在 Linux 上可访问
- [ ] Worker 能跑 jobs（并可通过 Admin enqueue）
- [ ] daily 可以定时触发（timer/cron/内置 scheduler 三选一）
- [ ] 日志可控（不会无限增长；支持轮转）
- [ ] 安全边界可配置（IP allowlist / basic auth / admin token）

### Windows DoD
- [ ] API + Admin 可用
- [ ] Jobs 能执行（至少不依赖 MinerU 的 job 必须可跑）
- [ ] 若 MinerU 不可用，清晰 fallback：WSL2 或远端执行 MinerU stage

---

## 6) 风险清单与缓解

1) **MinerU Windows 支持不确定**
- 缓解：把 MinerU stage 抽象成接口；支持 WSL2/remote/container 执行。

2) **SQLite 在服务器并发写入风险**
- 缓解：
  - 启用 WAL（如尚未）
  - 将 worker 并发控制为 1（或按 paper 粒度加锁）
  - 未来可切 Postgres（保持 Alembic 已接入）

3) **日志轮转跨平台差异**
- 缓解：用 Python logging 统一实现；OS 只负责启动。

4) **前端 PWA/SW 缓存导致更新不生效**
- 缓解：文档化更新策略；必要时提供“关闭 PWA”开关或加版本戳。

---

## 7) 建议的下一步（我建议先做的 3 件事）

1) Phase 0：完成 portability audit（把所有平台阻塞点列表化）
2) Phase 1：引入 `PAPERTOK_DATA_DIR` 并把 `.env.example` 彻底去绝对路径
3) Phase 2：落地 `papertokctl`（serve/worker/daily/doctor），把“能跑”从 bash/launchd 迁移到跨平台入口

> 这三件完成后，多平台的难点基本只剩 MinerU 和部署方式（systemd/Windows scheduler）。
