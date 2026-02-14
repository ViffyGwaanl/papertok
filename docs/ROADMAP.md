# PaperTok Roadmap（未来计划 / 准备事项）

> 原则：优先做“提升稳定性、可运维性、可迁移性”的工程任务；产品功能迭代在此基础上推进。

## 状态说明（已落地 / 已验证）
- ✅ Cloudflare Tunnel 公网入口 + Cloudflare Access 保护 `/admin*` 与 `/api/admin*`；后端 `X-Admin-Token` 双重校验。
- ✅ 域名规范化：`papertok.net/*` → `papertok.ai/$1`（301 永久重定向，保留 query）。
- ✅ 单服务同源：后端直接 serve 前端 dist；前端默认使用 `window.location.origin`（不再硬编码 `:8000`）。
- ✅ 前端 `API_BASE` 单点真理（`src/lib/apiBase.ts`），避免 WebView/同源/localhost 分叉。
- ✅ iOS/Android Capacitor internal build 已在真机安装运行；已记录 runbook。
- ✅ Android 内部分发链路：GitHub Releases + `.sha256` 校验；同时提供一个“永远指向最新”的稳定下载资产（`android-latest`）。
- ✅ ZH/EN 双语链路：schema + API `lang=zh|en|both` + pipeline + Web UI 切换；已完成 latest day 英文端到端回归。
- ✅ 双语回填已跑通并收敛：最近 7 天按“按天 8 指标验收”标准达标（减少 spam、进度可控）。
- ✅ Scheme B（release-based deploy）已稳定使用：releases + `current` 原子切换。
- ✅ prod shared 去 symlink 化已完成：`shared/.env`、`shared/data`、`shared/venv` 均为真实文件/目录（不再依赖 workspace checkout）。
- ✅ （已脱敏）支持额外的独立 tunnel 暴露本机内部服务入口（不在公开文档中披露域名与端口映射）。
- ✅ S0 安全收口完成：
  - `GET /api/status` 为公共摘要（不含本机路径/日志路径/敏感运维信息）
  - 新增 `GET /api/admin/status`（管理版）
  - `GET /api/papers/{id}` 不再暴露本机绝对路径
  - `ops/security_smoke.sh` 作为信息泄露回归测试

---

## P0（短期，1-3 天）：安全与稳定性收尾

1) **Cloudflare：强制 HTTPS（安全必做）**
- 在 Cloudflare 开启 *Always Use HTTPS*（或等价 Redirect Rule）
- 验收（对所有对外暴露的 hostname 都应成立）：
  - `curl -I http://papertok.ai/` 应返回 `301/308` → `https://papertok.ai/...`

2) **Cloudflare Access：保护所有“非公开/敏感入口”**
- 已保护：`/admin*` 与 `/api/admin*`。
- 若未来额外暴露任何内部服务入口（例如内部网关/工具服务），也必须一并纳入 Access（邮箱 allowlist）。

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

6) **健康检查/监控的 HTTP 方法兼容**
- 目前 `HEAD /healthz` 与 `HEAD /api/status` 可能返回 404（但 `GET` 是 200）。
- 两条路：
  - A) 外部健康检查统一改用 `GET`
  - B) 后端显式补 `@app.head` handlers（推荐做 B，减少误判）

---

## P1（中期，1-2 周）：运维工程化

1) **Release 保留策略（防磁盘膨胀）**
- 自动保留最近 N 个 releases，其余清理
- 清理策略需保证：`current` 指向的 release 永不删除

2) **备份/恢复策略**
- 脚本化：备份 SQLite + 关键数据目录（pdf/mineru/gen/logs）
- 提供“只备份 DB、衍生物可重算”的轻量模式

3) **配置健康检查（自检面板）**
- `/api/status`（public）或 `/api/admin/status`（admin）增加 health checklist：
  - LLM/VLM endpoint 可达？
  - Seedream/GLM key 是否存在？
  - MinerU CLI 是否存在？
  - 磁盘剩余空间、日志目录可写？

4) **更强的 Admin/Ops**
- 失败重试模板化（按 stage 一键重试）
- 支持按 `external_id` 搜索、按 stage 过滤、按 day 聚合

5) **公网入口的进一步防护（可选）**
- Cloudflare WAF/Rate limit（尤其对 `/api/papers/*`）
- 如果未来开放写入（点赞/收藏/评论等），必须先做 CSRF/鉴权设计

6) **磁盘清理策略（建议列入常规运维）**
- venv 只保留 prod shared/venv + dev（可选）
- 清理 HF/ModelScope cache 的 SOP（可接受“未来需要重新下载模型”的前提下）

---

## P2（长期）：可迁移/可扩展

1) **平台可迁移**
- 引入 `PAPERTOK_DATA_DIR`，把“代码路径”和“数据路径”彻底分离
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
