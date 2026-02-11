# Release-based Deployment (Scheme B)

This doc describes how to deploy PaperTok on a single Mac mini using:
- versioned releases under `DEPLOY_ROOT/releases/<id>`
- `DEPLOY_ROOT/current` symlink for the active version
- launchd LaunchAgents pointing to `DEPLOY_ROOT/current/...`

## Why
- Avoid editing code in-place on the running service
- Make deploy/rollback deterministic
- Reduce "half-deployed" states (e.g. frontend dist updated but backend not)

## Default paths
- `DEPLOY_ROOT=~/papertok-deploy`
- Shared state:
  - `~/papertok-deploy/shared/.env`
  - `~/papertok-deploy/shared/data/`
  - `~/papertok-deploy/shared/venv/` (optional)

## One-time setup (safe, no downtime)
```bash
cd papertok
ops/release/prepare_shared.sh
```

## Build a new release (safe; CPU/IO heavy)
```bash
cd papertok
ops/release/build_release.sh
ls -la ~/papertok-deploy/releases
```

## Install LaunchAgents for release mode (requires service restart)
```bash
cd papertok
ops/launchd/install_release_current.sh
```

## Switch to a release (brief downtime)
```bash
cd papertok
ops/release/switch_current.sh <release-id>
```

Notes:
- 尽量避免在**长耗时 jobs 正在运行**时切换（例如英文/中文生图、全量图注回填）。
  - 切换会重启 server/worker，可能导致当前 running job 中断或重复。
  - 推荐做法：先让队列跑空/关键 job 完成，再原子切换。

## Rollback
Switch `current` back to a previous release id and restart services:
```bash
ops/release/switch_current.sh <old-release-id>
```

## Phases (recommended)

### Phase 1: Start with shared as symlinks (lowest risk)
`ops/release/prepare_shared.sh` intentionally creates symlinks to your existing checkout:
- `shared/.env -> <repo>/.env`
- `shared/data -> <repo>/data`
- `shared/venv -> <repo>/backend/.venv`

This is the safest way to adopt Scheme B without moving state.

### Phase 2: De-symlink shared (production hardening)
After Scheme B proves stable, migrate shared to be **real files/directories** under `DEPLOY_ROOT/shared/`:
- `shared/.env` becomes a real file (copied from old `.env`)
- `shared/data` becomes a real directory (migrated from old `data/`)
- optionally rebuild `shared/venv` as a real venv

Benefits:
- prod no longer depends on your dev/workspace checkout
- reduces risk of accidental prod breakage when editing/cleaning workspace

## Notes / Pitfalls

### Python version (macOS)
Prefer **Python 3.13** for venv creation.
On macOS, Python 3.14 may fail installing `pydantic-core` due to Rust/PyO3 version checks.

### Disk space
Rebuilding a full venv with MinerU/torch/opencv is large.
Before rebuilding `shared/venv`, ensure you have multiple GB of free space.

Also note:
- `DEPLOY_ROOT/releases/*` 会持续累积（每次 build_release 都会生成一个新目录）。
- 建议制定保留策略：只保留最近 N 个 release，且永不删除 `current` 指向的版本。

### Current hardening status
- `.env` and `data/` are designed to live outside releases.
- For maximum isolation, replace `shared/venv` symlink with an independent venv.
