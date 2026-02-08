# PaperTok 文档索引（Handbook）

> 适用场景：本地在 Mac mini 上长期运行 PaperTok（后端单服务托管前端），每天抓取 Hugging Face Daily Papers 当天 Top10，离线跑完整流水线，并提供 Admin/Ops 面板用于运维。

## 快速事实（TL;DR）
- 主域（canonical）：`https://papertok.ai`
- 别名域：`https://papertok.net`（**301 永久重定向**到 `papertok.ai`）
- Admin 面：Cloudflare Access（邮箱白名单）+ 后端 `X-Admin-Token` 双重保护
- Android 分发：release 签名 APK，推荐通过 **GitHub Releases** 分发（附带 `.sha256`）

## 目录

1. [总体概览](./Handbook.md#1-总体概览)
2. [快速开始（开发/生产本地）](./Handbook.md#2-快速开始)
3. [架构与关键设计决策](./Handbook.md#3-架构与关键设计决策)
4. [数据目录与数据模型](./Handbook.md#4-数据目录与数据模型)
5. [配置：.env 与 DB Config 的边界](./Handbook.md#5-配置体系env-vs-db-config)
6. [API 说明](./Handbook.md#6-api-说明)
7. [流水线与可观测性（paper_events）](./Handbook.md#7-流水线与可观测性)
8. [Admin / Jobs / Worker 运维](./Handbook.md#8-admin--jobs--worker-运维)
9. [launchd 与日志轮转（macOS）](./Handbook.md#9-launchd-与日志轮转macos)
10. [安全边界（LAN 安全）](./Handbook.md#10-安全边界lan-安全)
11. [故障排查 Runbook](./Handbook.md#11-故障排查-runbook)
12. [项目历史 / 已完成工作清单](./HISTORY.md)
13. [Roadmap（未来计划）](./ROADMAP.md)
14. [多平台兼容计划（Server + Windows）](./PLATFORM_PLAN.md)
15. [公网发布方案（本地 Mac mini 重算力 + 公网 VPS 入口）](./PUBLIC_INGRESS_PLAN.md)
16. [Cloudflare Tunnel 优先：无 VPS 先上线公网](./CLOUDFLARE_TUNNEL_PLAN.md)
17. [移动端 App 计划（iOS/Android：PWA → Capacitor → 可选原生重写）](./MOBILE_APP_PLAN.md)
18. [移动端 App 实施方案（Internal Build）](./MOBILE_APP_IMPLEMENTATION.md)
19. [iOS App 计划（阶段 1：仅公网 HTTPS）](./IOS_APP_PLAN.md)
20. [Android App 计划（阶段 1：仅公网 HTTPS）](./ANDROID_APP_PLAN.md)
21. [App 内部安装指南（iOS/Android，本地签名/运行）](./APP_INTERNAL_RUNBOOK.md)
22. [papertok.ai / papertok.net 上线步骤（Cloudflare Tunnel，无 VPS）](./DEPLOY_PAPERTOK_AI_NET_CLOUDFLARE.md)
23. [Android APK 发布（给别人安装）](./ANDROID_APK_RELEASE.md)
24. [安全模型（Defense in Depth）](./SECURITY.md)

---

## 读法建议
- 你要“现在怎么跑起来”：直接看 `Handbook.md` 的第 2 章。
- 你要“为什么这么设计”：看第 3 章。
- 你要“运维怎么做”：看第 8、9、11 章。
