# PaperTok launchd 安装指南（macOS）

## 推荐的 LaunchAgents（长期常驻/周期）
只建议长期 load 这 4 个：
- **server（常驻）**：`com.papertok.server`
- **job_worker（常驻轮询队列）**：`com.papertok.job_worker`
- **daily（每天定时）**：`com.papertok.daily`
- **logrotate（每天定时）**：`com.papertok.logrotate`

> 说明：
> - “一次性重任务”（image_caption / paper_images / *_regen / *_backfill 等）已经被 **Admin → Jobs** 取代，默认不建议长期 load。
> - `com.papertok.daily` 是“模式 C（重）”端到端流水线；为了避免 **重启/重新 load 时立刻开跑**，plist 已设置 `RunAtLoad=false`。

## 一键安装/更新（推荐）
在仓库根目录 `papertok/` 下执行：

```bash
bash ops/launchd/install_core.sh
```

它会把 4 个核心 plist 复制到 `~/Library/LaunchAgents/` 并 load，然后 kickstart server + worker。

## 查看状态
```bash
launchctl list | rg com\.papertok
```

## 查看日志
日志目录：`papertok/data/logs/`

常用：
```bash
tail -n 200 papertok/data/logs/server.err.log

tail -n 200 papertok/data/logs/job_worker.launchd.err.log

tail -n 200 papertok/data/logs/daily.err.log
```

## 停止/卸载（核心 4 个）
```bash
for f in com.papertok.server com.papertok.job_worker com.papertok.daily com.papertok.logrotate; do
  launchctl unload "$HOME/Library/LaunchAgents/$f.plist" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/$f.plist"
done
```

## 清理“可选的一次性重任务” LaunchAgents（推荐做一次）
如果你之前 load 过很多一次性任务（会导致开机/登录后自动跑重活），可以运行：

```bash
bash ops/launchd/prune_optional.sh
```

它会 unload 并把对应 plist 重命名为 `*.disabled.<timestamp>`，可随时恢复。
