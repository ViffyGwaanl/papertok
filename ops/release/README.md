# Release-based Deployment (Scheme B)

This project supports a **release + `current` symlink** deployment workflow.

Goal:
- Build a versioned snapshot under `DEPLOY_ROOT/releases/<id>`
- Atomically switch `DEPLOY_ROOT/current` to the new release
- Restart launchd services to pick up the new code
- Fast rollback by switching `current` back

Default `DEPLOY_ROOT`:
- `~/papertok-deploy`

Layout:
```
~/papertok-deploy/
  releases/<release-id>/    # immutable snapshots
  current -> releases/...   # active release
  shared/
    .env                    # secrets (symlink/copy)
    data/                   # sqlite/logs/pdfs/mineru output (symlink/copy)
    venv/                   # python venv used by releases (optional)
```

Scripts:
- `ops/release/prepare_shared.sh` – create `DEPLOY_ROOT/shared` (safe; no downtime)
- `ops/release/build_release.sh` – create a new release snapshot (safe; CPU/IO heavy)
- `ops/release/switch_current.sh` – point `current` to a release + restart services (brief downtime)

LaunchAgents:
- Use `ops/launchd/install_release_current.sh` to install LaunchAgents that point to
  `DEPLOY_ROOT/current/...`.
