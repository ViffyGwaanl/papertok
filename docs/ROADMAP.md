# PaperTok Roadmap（未来计划 / 准备事项）

> 原则：优先做“提升稳定性、可运维性、可迁移性”的工程任务；产品功能迭代在此基础上推进。

## 状态说明
- **已落地**：Cloudflare Tunnel 公网入口 + Cloudflare Access 保护 `/admin*` 与 `/api/admin*`；后端 `X-Admin-Token` 双重校验。
- **已修复**：公网/移动端同源加载（前端默认使用 `window.location.origin`；不再硬编码 `:8000`）。
- **已落地**：前端 `API_BASE` 单点真理（`src/lib/apiBase.ts`），避免 WebView/同源/localhost 分叉。
- **已验收**：iOS/Android Capacitor internal build 已在真机安装运行（本地 Xcode/Android Studio）。
- **S0 安全收口完成**：
  - `GET /api/status` 变为公共摘要（不含本机路径/日志路径/敏感运维信息）
  - 新增 `GET /api/admin/status`（管理版）
  - `GET /api/papers/{id}` 不再暴露本机绝对路径
  - 新增 `ops/security_smoke.sh` 作为信息泄露回归测试

---

## P0（短期，1-3 天）：稳定性/体验收尾

1) **前端可诊断性（Loading 卡住时能自救）**
- 在 UI 上显示更明确的错误态（比如“请求失败/网络错误/权限被拦截”），并提供一键重试
- 对 `/api/papers/random` 与 `/api/papers/{id}` 增加超时 + 重试策略（有限次数）
- 在详情弹窗里区分：讲解缺失 vs 请求失败

2) **Jobs 兜底操作（运维必备）**
- Admin 增加：
  - cancel queued job
  - mark running → failed（人工止血）
- worker stale job 策略进一步明确：超时阈值、重试次数、是否允许并发

3) **/api/status 语义优化**
- 现在 `failed_by_stage` 是历史累计；建议补一个“当前未解决失败”视图：
  - per paper 只取最近一次事件，或用 DB 缺失字段作为“当前状态”
- 面板上减少“历史失败把人吓到”的噪声

4) **MinerU warning 噪声治理**
- 处理 `cv2` 与 `av` dylib duplicate class 警告，降低“神秘崩溃”风险

5) **Internal 分发/打包（可选，但能显著降低安装成本）**
- iOS：补一份“Archive → Export .ipa（Development）→ 安装”的 runbook（不等同于永久分发；Personal Team 仍会过期）
- Android：输出 debug APK / release APK（签名与版本号策略），便于不依赖 Android Studio 安装
- 若决定给多人分发：
  - iOS：Apple Developer Program + TestFlight
  - Android：Play 内测 / 直接分发 APK

---

## P1（中期，1-2 周）：运维工程化

1) **备份/恢复策略**
- 脚本化：备份 SQLite + 关键数据目录（pdf/mineru/gen/logs）
- 提供“只备份 DB、衍生物可重算”的轻量模式

2) **配置健康检查（自检面板）**
- `/api/status` 增加 health checklist：
  - LLM/VLM endpoint 可达？
  - Seedream/GLM key 是否存在？
  - MinerU CLI 是否存在？
  - 磁盘剩余空间、日志目录可写？

3) **更强的 Admin/Ops**
- 失败重试模板化（按 stage 一键重试）
- 支持按 `external_id` 搜索、按 stage 过滤、按 day 聚合

4) **公网入口的进一步防护（可选）**
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
