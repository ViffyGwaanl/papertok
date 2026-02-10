# Dev 环境：全流程回归（冻结论文数据集）

目标：
- **dev 也能跑全流程**（MinerU → explain → captions → paper_images）用于回归测试
- **不新增论文**（不再从 Hugging Face 拉新 Top10，不新增 papers 记录）
- dev 与 prod **数据/DB/依赖隔离**，避免误伤线上

> 典型用法：线上稳定跑 prod；你在 dev 里对“同一批论文”反复 wipe+重跑，验证提示词/模型/脚本改动的影响。

---

## 推荐目录布局

- **prod（线上）**：`~/papertok-deploy/current`（Scheme B release 部署）
- **dev（回归）**：`~/papertok-dev/repo`
- dev 的 shared：
  - `~/papertok-dev/shared/.env`
  - `~/papertok-dev/shared/data/`
  - `~/papertok-dev/shared/venv/`

dev 仓库中建议用 symlink 保持“项目根目录单一事实源”习惯：
- `~/papertok-dev/repo/.env -> ~/papertok-dev/shared/.env`
- `~/papertok-dev/repo/data -> ~/papertok-dev/shared/data`
- `~/papertok-dev/repo/backend/.venv -> ~/papertok-dev/shared/venv`

---

## 冻结数据集的关键设置（必须）

在 **dev 的 `.env`** 中设置：

```bash
# Freeze dataset: do NOT fetch new HF daily papers
HF_TOP_N=0

# Use cached PDFs only (no new downloads)
DOWNLOAD_PDF=0
```

这样 dev 即使跑全流程，也只会对 **DB 里已有的 papers** 做处理/重跑。

---

## Python 版本建议

建议 dev 使用 **Python 3.13** 创建 venv。

原因：在 macOS 上 Python 3.14 可能触发 `pydantic-core` 的 Rust/PyO3 编译兼容问题（安装失败），3.13 有现成 wheel 更稳。

---

## 从 prod 拷贝一份“测试数据快照”（一次性）

建议用：
- SQLite：用 `sqlite3 .backup` 做一致性快照
- `data/` 资产：`rsync` 拷贝（pdf/mineru/gen_images 等）

示例（按你的实际路径调整）：

```bash
# 1) DB 备份
sqlite3 ~/papertok-deploy/shared/data/db/papertok.sqlite \
  ".backup '$HOME/papertok-dev/shared/data/db/papertok.sqlite'"

# 2) 拷贝 data 资产（建议排除 logs，避免噪声）
rsync -a \
  --exclude 'logs/' \
  --exclude 'db/papertok.sqlite' \
  "$HOME/papertok-deploy/shared/data/" \
  "$HOME/papertok-dev/shared/data/"
```

---

## dev 启动与跑全流程（只跑现有论文）

### 启动 dev server（本地端口）
在 dev `.env` 中用不同端口（示例）：

```bash
PAPERTOK_HOST=127.0.0.1
PAPERTOK_PORT=8001
```

启动：
```bash
cd ~/papertok-dev/repo
bash ops/run_server.sh
```

### 跑全流程回归（不新增 papers）
推荐使用 dev 专用脚本（见 `ops/dev/run_full_pipeline_existing.sh`）：

```bash
cd ~/papertok-dev/repo
bash ops/dev/run_full_pipeline_existing.sh
```

> 注意：不要用 `ops/run_daily.sh` 在 dev 跑回归，因为它默认会强制 `HF_TOP_N=10`（会尝试拉新 Top10）。

---

## 常见误区

1) **data 分两份会不会导致后台跑两套？**
- 不会。是否“双跑”只取决于你是否同时启动两套后台（两套 launchd / 两个终端进程）。
- 推荐：prod 由 launchd 管；dev 默认不 load 定时任务，只手动跑。

2) **dev 想反复回归，但为什么不重新生成？**
- 因为脚本通常是“pending-only”。回归测试往往需要先 wipe 产物字段/表，再重跑。
- 可以逐步完善 dev 的 wipe 脚本（例如清空 `content_explain_cn` / `image_captions_json` / `paper_images`）。
