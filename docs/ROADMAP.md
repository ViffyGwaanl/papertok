# PaperTok Roadmap（未来计划 / 准备事项）

> 原则：优先做“提升稳定性、可运维性、可迁移性”的工程任务；产品功能迭代在此基础上推进。

## P0（短期，1-3 天）：稳定性/体验收尾

1) **/api/status 语义优化**
- 现在 `failed_by_stage` 是历史累计；建议补一个“当前未解决失败”视图：
  - 对每篇 paper 取最新事件/或以 DB 状态（缺失字段）为准
  - 面板上减少“历史失败把人吓到”的噪声

2) **Jobs 卡死处理**
- 增加 Admin 操作：
  - mark running → failed（人工兜底）
  - 或 cancel queued job
- worker 对 stale job 的策略进一步文档化

3) **MinerU warning 噪声治理**
- 处理 `cv2` 与 `av` dylib duplicate class 警告，降低“神秘崩溃”风险

---

## P1（中期，1-2 周）：运维工程化

1) **日志与指标**
- 将 job_worker / server / daily 的关键指标在 `/api/status` 输出更结构化：
  - last_run_at / last_success_at / last_error
- 可选：增加 Prometheus 格式 metrics（不引入太重依赖也可）

2) **数据备份/恢复**
- 提供脚本：备份 SQLite + data/raw + data/mineru 的策略
- 提供“只备份 DB + 重新生成衍生物”的策略（更轻）

3) **配置健康检查**
- 在 `/api/status` 增加“配置自检”：
  - 模型端点可达？
  - Seedream/GLM key 是否存在？
  - MinerU CLI 是否存在？

---

## P2（长期）：可迁移/可扩展

1) **数据库迁移**
- SQLite → Postgres（如未来多用户/并发写入上来）

2) **分布式 Worker**
- 如果未来要把生成任务放到另一台机器/服务器，可把 Jobs 扩展为多 worker 消费

3) **更强的 Admin/Ops**
- 失败重试策略模板化（按 stage 一键重试）
- 事件面板支持按 external_id 搜索、按 stage 过滤、按 day 聚合

4) **前端体验**
- 竖滑/轮播在更多移动端浏览器一致性验证
- 增加“过滤/只看某天/只看某 provider”的 UI

---

## 准备事项（你现在可以提前做的）

- 预留一个“生产目录结构”标准：
  - `/opt/papertok` 代码
  - `/var/lib/papertok` 数据（db/raw/mineru/gen/logs）
- 把 `.env` 做成分环境：`.env.local` / `.env.prod`（由启动脚本选择）
- 给关键脚本加上 `--dry-run` 和更清晰的输出（便于排障）
