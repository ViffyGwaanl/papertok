# launchd (macOS) — PaperTok 运维

## 总原则（工程化）
- **常驻/周期**：只保留少量、明确职责的 LaunchAgents（server / job_worker / daily / logrotate）。
- **一次性重任务**：不要长期 load（否则机器重启/重新 load 时会“自动跑重活”）。
  - 统一走 **Admin → Jobs enqueue**（可观察、可重试、日志归档到 job log）。

当前仓库里仍保留了一些“历史 one-shot plist”，但已做成 **RunAtLoad=false**，仅用于手工 kickstart 调试。

---

## 推荐安装（核心 4 个）
在 `papertok/` 目录执行：

```bash
bash ops/launchd/install_core.sh
```

核心列表：
- `com.papertok.server`：后端 API + 静态前端
- `com.papertok.job_worker`：轮询 jobs 队列并执行
- `com.papertok.daily`：每天定时跑（模式 C：当天 Top10 端到端）
- `com.papertok.logrotate`：轮转 `data/logs/*.log`

查看：
```bash
launchctl list | rg com\.papertok
```

---

## 一次性任务（推荐方式）
去 `http://127.0.0.1:8000/admin`：
- Enqueue 各类 job（caption fill/regen、paper_images、paper_events_backfill、per-paper retry…）
- tail job log

不建议再 load 下面这些 old plists：
- `com.papertok.image_caption*`
- `com.papertok.paper_images*`
- `com.papertok.content_analysis`

如果你之前 load 过它们，建议做一次清理：
```bash
bash ops/launchd/prune_optional.sh
```

---

## 日志
日志目录：`papertok/data/logs/`

- server：`server.out.log` / `server.err.log`
- worker：`job_worker.launchd.out.log` / `job_worker.launchd.err.log`
- daily：`daily.out.log` / `daily.err.log`

轮转：`com.papertok.logrotate` 会按阈值 copy+truncate（不会破坏运行中进程的 file handle）。

---

## 常用命令
重启 server：
```bash
launchctl kickstart -k gui/$(id -u)/com.papertok.server
```

重启 worker：
```bash
launchctl kickstart -k gui/$(id -u)/com.papertok.job_worker
```
