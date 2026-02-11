# Platform Portability & Deployability Plan (Server + Windows)

[English](./PLATFORM_PLAN.md) | [中文](../PLATFORM_PLAN.md)

Goal: evolve PaperTok from “Mac mini local MVP” into:
- stable **Linux server** deployment (worker, scheduler, logs, security boundary)
- runnable on **Windows** locally (at least API + UI + Jobs/worker; MinerU may require fallback)

This plan is organized by scope/goals, principles, minimal architecture changes, milestones, DoD, and risks.

---

## 1) Scope & goals

### Target platforms
- macOS (keep supporting; launchd is just one runner)
- Linux server (Ubuntu 22.04/24.04; systemd or containers)
- Windows 11 (native Python; optionally WSL2/containers)

### Compatibility tiers
- L0: API starts, UI accessible, DB works, static files served
- L1: Jobs queue + worker works; Admin can enqueue and tail logs
- L2: Daily scheduler works cross-platform
- L3: Production-grade server deployment (TLS, reverse proxy, rate limits, backups, monitoring, multi-worker)

Non-goals (short term)
- Multi-tenant auth system
- Mandatory distributed queue (Redis/Celery)
- Large write concurrency (SQLite is sufficient for now; later Postgres)

---

## 2) Key principles
1) Do not depend on launchd at runtime: systemd/Windows services should be thin wrappers.
2) Paths and data dirs must be configurable/relocatable (no hard-coded `/Users/...`).
3) Config layering: `.env` for secrets/paths; DB config for runtime toggles.
4) Logging/rotation should be unified at the app level (Python logging).
5) Must be testable (CI for lint/build/py_compile).

---

## 3) Minimal architecture changes

### 3.1 Standardize processes
- `papertok-api` (FastAPI)
- `papertok-worker` (Jobs consumer)
- `papertok-scheduler` (optional)

### 3.2 Introduce a unified CLI (`papertokctl`)
Provide commands:
- `serve`, `worker`, `daily`, `logrotate`, `doctor`

### 3.3 Data directory abstraction
- Introduce `PAPERTOK_DATA_DIR` defaulting to `<repo>/data`.

### 3.4 Platform-specific dependency strategy
- MinerU on Windows may need WSL2/remote/container fallback.
- `qpdf` install differs per OS; `doctor` should print actionable guidance.

---

## 4) Milestones (WBS)
- Phase 0: portability audit
- Phase 1: migratable paths/config defaults
- Phase 2: CLI replaces bash ops scripts
- Phase 3: Linux deployment (systemd and/or docker-compose)
- Phase 4: Windows support + MinerU fallback story
- Phase 5: CI gates

---

## 5) Definition of Done
- Linux: API/Admin accessible; worker runs jobs; scheduling works; logs rotate; security boundary configurable.
- Windows: API/Admin accessible; jobs run (at least non-MinerU jobs); clear MinerU fallback plan.

---

## 6) Risks & mitigations
- MinerU Windows uncertainty → abstract stage + fallback.
- SQLite concurrency → WAL + worker concurrency control; later Postgres.
- Cross-platform log rotation → use Python logging.
- PWA/SW cache surprises → document hard reload and version stamps.
