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

## Rollback
Switch `current` back to a previous release id and restart services:
```bash
ops/release/switch_current.sh <old-release-id>
```

## Notes
- This workflow keeps `data/` and `.env` outside releases (symlinked), so state persists.
- For maximum isolation, replace `shared/venv` symlink with an independent venv.
