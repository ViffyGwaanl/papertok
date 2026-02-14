# Release-based Deployment (Scheme B)

[English](./RELEASE_DEPLOYMENT.md) | [中文](../RELEASE_DEPLOYMENT.md)

This doc describes how to deploy PaperTok on a single Mac mini using:
- versioned releases under `DEPLOY_ROOT/releases/<id>`
- `DEPLOY_ROOT/current` symlink for the active version
- launchd LaunchAgents pointing to `DEPLOY_ROOT/current/...`

---

## Why
- Avoid editing code in-place on a running service
- Deterministic deploy/rollback
- Reduce “half-deployed” states (e.g. frontend updated but backend not)

## Default paths
- `DEPLOY_ROOT=~/papertok-deploy`
- Shared state:
  - `~/papertok-deploy/shared/.env`
  - `~/papertok-deploy/shared/data/`
  - `~/papertok-deploy/shared/venv/` (prod Python venv)

---

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

## Install LaunchAgents for release mode (requires restart)
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
- Avoid switching while long-running jobs are active.
  - Switching restarts server/worker and may interrupt or duplicate the running job.
  - Recommended: let the queue drain (or finish critical jobs), then switch atomically.

---

## Rollback
Switch `current` back to a previous release and restart services:
```bash
ops/release/switch_current.sh <old-release-id>
```

---

## Recommended adoption phases

### Phase 1: shared as symlinks (lowest risk)
`ops/release/prepare_shared.sh` intentionally creates symlinks to your existing checkout:
- `shared/.env -> <repo>/.env`
- `shared/data -> <repo>/data`
- `shared/venv -> <repo>/backend/.venv`

This is the safest way to adopt Scheme B without moving state.

### Phase 2: de-symlink shared (production hardening)
After Scheme B proves stable, migrate shared to be real files/dirs under `DEPLOY_ROOT/shared/`:
- `shared/.env` becomes a real file
- `shared/data` becomes a real directory
- `shared/venv` becomes a real venv directory

Benefits:
- prod no longer depends on your dev/workspace checkout
- reduces risk of accidental production breakage when cleaning/editing workspace

---

## Current hardening status (recommended target state)

In a hardened setup:
- `~/papertok-deploy/shared/.env` is a **real file**
- `~/papertok-deploy/shared/data` is a **real directory**
- `~/papertok-deploy/shared/venv` is a **real venv directory** (Python 3.13 recommended)
- `~/papertok-deploy/current/backend/.venv` is a **symlink** to `~/papertok-deploy/shared/venv`

This lets you safely clean workspace/dev checkouts without breaking production.

---

## Migrating `shared/venv`: symlink → real directory

This step is optional but strongly recommended.

### Option A (recommended): copy an existing venv (fast, safest)

```bash
# Example paths (adjust as needed)
SRC=/path/to/old/.venv
DEPLOY_ROOT=~/papertok-deploy
TMP="$DEPLOY_ROOT/shared/venv.__tmp__"

rm -rf "$TMP"
mkdir -p "$TMP"
rsync -a --delete "$SRC/" "$TMP/"

# validate
"$TMP/bin/python" -c 'import mineru; print("mineru ok")'

# swap atomically
mv "$DEPLOY_ROOT/shared/venv" "$DEPLOY_ROOT/shared/venv.bak.$(date +%Y%m%d-%H%M%S)"
mv "$TMP" "$DEPLOY_ROOT/shared/venv"
```

Then ensure the current release uses it:
```bash
ln -sfn "$DEPLOY_ROOT/shared/venv" "$DEPLOY_ROOT/current/backend/.venv"
```

### Option B: rebuild venv from scratch
Prefer Python 3.13. MinerU/torch/opencv make this slow and large.

---

## Notes / pitfalls

### Python version (macOS)
Prefer **Python 3.13** for venv creation.
On macOS, Python 3.14 may fail to install `pydantic-core` due to Rust/PyO3 compatibility checks.

### Disk space
A full venv with MinerU/torch/opencv is large.
Before rebuilding `shared/venv`, ensure you have multiple GB of free space.

Releases accumulate under `DEPLOY_ROOT/releases/*`.
Define a retention policy: keep last N releases, and never delete the version pointed to by `current`.
