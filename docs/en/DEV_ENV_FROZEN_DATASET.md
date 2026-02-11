# Dev Environment: Full Pipeline Regression (Frozen Dataset)

[English](./DEV_ENV_FROZEN_DATASET.md) | [中文](../DEV_ENV_FROZEN_DATASET.md)

Goals:
- Run the full pipeline in dev (MinerU → explain → captions → images) for regression testing
- Do **not** ingest new papers (no new HF Top10; no new `papers` rows)
- Isolate dev from prod (DB/data/deps) to avoid accidental production damage

Typical usage: prod runs stably; dev repeatedly wipes and regenerates on the *same dataset* to validate prompt/model/script changes.

---

## Recommended directory layout
- **Prod**: `~/papertok-deploy/current` (Scheme B releases)
- **Dev repo**: `~/papertok-dev/repo`
- Dev shared state:
  - `~/papertok-dev/shared/.env`
  - `~/papertok-dev/shared/data/`
  - `~/papertok-dev/shared/venv/`

Recommended symlinks inside dev repo:
- `~/papertok-dev/repo/.env -> ~/papertok-dev/shared/.env`
- `~/papertok-dev/repo/data -> ~/papertok-dev/shared/data`
- `~/papertok-dev/repo/backend/.venv -> ~/papertok-dev/shared/venv`

---

## Required settings to freeze the dataset
In dev `.env`:

```bash
# Freeze dataset: do NOT fetch new HF daily papers
HF_TOP_N=0

# Use cached PDFs only (no new downloads)
DOWNLOAD_PDF=0
```

With these, dev runs only on existing papers already in the DB.

---

## Python version
Use **Python 3.13** for venv on macOS.
Reason: Python 3.14 may hit `pydantic-core` Rust/PyO3 build compatibility issues; 3.13 has stable wheels.

---

## One-time: copy a prod snapshot into dev
Recommended:
- SQLite: use `sqlite3 .backup` for a consistent snapshot
- `data/` assets: `rsync` (pdf/mineru/generated images, etc.)

Example:

```bash
# 1) DB snapshot
sqlite3 ~/papertok-deploy/shared/data/db/papertok.sqlite \
  ".backup '$HOME/papertok-dev/shared/data/db/papertok.sqlite'"

# 2) Copy data assets (exclude logs)
rsync -a \
  --exclude 'logs/' \
  --exclude 'db/papertok.sqlite' \
  "$HOME/papertok-deploy/shared/data/" \
  "$HOME/papertok-dev/shared/data/"
```

---

## Start dev server & run full regression (existing dataset only)

### Start dev server on a different port
In dev `.env`:
```bash
PAPERTOK_HOST=127.0.0.1
PAPERTOK_PORT=8001
```

Start:
```bash
cd ~/papertok-dev/repo
bash ops/run_server.sh
```

### Run full regression
Use the dev script:
```bash
cd ~/papertok-dev/repo
bash ops/dev/run_full_pipeline_existing.sh
```

> Do NOT use `ops/run_daily.sh` for regression in dev: it forces `HF_TOP_N=10` by default.

---

## Common pitfalls

1) “Will I run two pipelines if I have two data dirs?”
- No. Double runs only happen if you start two servers/workers (two launchd setups or two terminal processes).

2) “Why didn’t it regenerate in dev?”
- Most scripts are pending-only. Regression usually requires wiping the target fields/tables first, then rerunning.
