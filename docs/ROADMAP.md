# PaperTok Roadmap（未来计划 / 准备事项）

> 原则：优先做“提升稳定性、可运维性、可迁移性”的工程任务；产品功能迭代在此基础上推进。

## 状态说明
- **已落地**：Cloudflare Tunnel 公网入口 + Cloudflare Access 保护 `/admin*` 与 `/api/admin*`；后端 `X-Admin-Token` 双重校验。
- **已落地**：域名规范化：`papertok.net/*` → `papertok.ai/$1`（301 永久重定向，保留 query）。
- **已修复**：公网/移动端同源加载（前端默认使用 `window.location.origin`；不再硬编码 `:8000`）。
- **已落地**：前端 `API_BASE` 单点真理（`src/lib/apiBase.ts`），避免 WebView/同源/localhost 分叉。
- **已验收**：iOS/Android Capacitor internal build 已在真机安装运行（本地 Xcode/Android Studio）。
- **已落地**：Android release APK 发布链路（GitHub Releases + `.sha256`），并记录了 iCloud/互传目录可能导致后台读取失败（`Resource deadlock avoided`）的限制与规避方法。
- **已落地**：ZH/EN 双语链路（schema + API `lang=zh|en|both` + pipeline + Web UI `中文/EN` 切换），并完成 latest day 英文端到端回归。
- **已修复**：移动端语言切换竞态（切换后外层 one-liner 残留旧语言）——需要通过重新打包 App 获取修复。
- **S0 安全收口完成**：
  - `GET /api/status` 变为公共摘要（不含本机路径/日志路径/敏感运维信息）
  - 新增 `GET /api/admin/status`（管理版）
  - `GET /api/papers/{id}` 不再暴露本机绝对路径
  - 新增 `ops/security_smoke.sh` 作为信息泄露回归测试

---

## P0（短期，1-3 天）：稳定性/体验收尾

1) **Cloudflare：强制 HTTPS（安全必做）**
- 在 Cloudflare 开启 *Always Use HTTPS*（或等价 Redirect Rule）
- 验收：`curl -I http://papertok.ai/` 应返回 `301/308` → `https://papertok.ai/...`

2) **双语生产回填（让 EN 真正“可用”）**
- latest day 已完成 EN 端到端（one-liner/explain/caption/images）。
- 已增加“按天完成验收”监控脚本（8 指标严格达标才汇报），用于减少 spam、让回填进度更可控。
- 下一步选择回填范围：
  - A) 最近 7/30 天
  - B) 全量历史（成本较高，需限速/排队）
- 为回填建立标准作业：按 `day`/`lang` 分批 enqueue（避免全库一次性跑崩）

3) **前端可诊断性（Loading 卡住时能自救）**
- 在 UI 上显示更明确的错误态（请求失败/权限被拦截/离线缓存命中），并提供一键重试
- 对 `/api/papers/random` 与 `/api/papers/{id}` 增加超时 + 有限次数重试
- 在详情弹窗里区分：讲解缺失 vs 请求失败

4) **Jobs 兜底操作（运维必备）**
- Admin 增加：
  - cancel queued job
  - mark running → failed（人工止血）
- worker stale job 策略进一步明确：超时阈值、重试次数、是否允许并发

5) **/api/status 语义优化**
- 现在 `failed_by_stage` 是历史累计；建议补一个“当前未解决失败”视图：
  - per paper 只取最近一次事件，或用 DB 缺失字段作为“当前状态”
- 面板上减少“历史失败把人吓到”的噪声

6) **Internal 分发/打包（让 App 跟上 Web 功能）**
- 结论：App 壳不会自动更新 Web 前端；每次前端变更都需要重新打包/发布（这也是为什么 App 里“语言切换问题”无法靠刷新解决）。
- iOS：补齐 “Archive → TestFlight” 或 “Development .ipa” 的 runbook
- Android：release 签名 APK + GitHub Releases 分发
  - 注意：不要把待上传 APK 放在 iCloud/互传目录（可能触发 `Resource deadlock avoided`）；先拷到本地路径再上传

---

## P1（中期，1-2 周）：运维工程化

0) **完成 Scheme B 最后一块隔离：prod `shared/venv`**
- 用 Python 3.13 重建 `~/papertok-deploy/shared/venv`（避免 3.14 的 pydantic-core/PyO3 坑）
- 安装依赖时建议 `PIP_NO_CACHE_DIR=1`，降低磁盘峰值
- 增加磁盘空间检查（free space < 阈值直接 fail-fast）

1) **Release 保留策略（防磁盘膨胀）**
- 自动保留最近 N 个 releases，其余清理
- 清理策略需保证：current 指向的 release 永不删除

2) **备份/恢复策略**
- 脚本化：备份 SQLite + 关键数据目录（pdf/mineru/gen/logs）
- 提供“只备份 DB、衍生物可重算”的轻量模式

3) **配置健康检查（自检面板）**
- `/api/status` 增加 health checklist：
  - LLM/VLM endpoint 可达？
  - Seedream/GLM key 是否存在？
  - MinerU CLI 是否存在？
  - 磁盘剩余空间、日志目录可写？

4) **更强的 Admin/Ops**
- 失败重试模板化（按 stage 一键重试）
- 支持按 `external_id` 搜索、按 stage 过滤、按 day 聚合

5) **公网入口的进一步防护（可选）**
- Cloudflare WAF/Rate limit（尤其对 `/api/papers/*`）
- 只要未来开放写入（点赞/收藏/评论等），必须先做 CSRF/鉴权设计

---

## P2（长期）：可迁移/可扩展

1) **平台可迁移**
- 抽象数据目录（如引入 `PAPERTOK_DATA_DIR`），把“代码路径”和“数据路径”彻底分离
- 逐步实现 Linux server / Windows 本地运行（见 `PLATFORM_PLAN.md`）

2) **数据库演进**
- 如果未来多用户或并发写入明显增加：SQLite → Postgres

3) **分布式 Worker**
- 多 worker 消费 Jobs（把生成任务拆到另一台机器/服务器）

4) **移动端 App 壳**
- PWA → Capacitor internal build（见 `MOBILE_APP_IMPLEMENTATION.md`）

---

## 工程管理（建议尽早决定）

- **GitHub 同步策略**：当前是“导出快照式导入”。建议选一种长期方式：
  1) 直接把 workspace 里的 `papertok/` 变成独立 git repo（推荐）
  2) 保持导出，但改为“可增量历史”的发布脚本（稍复杂）
