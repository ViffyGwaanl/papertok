# PaperTok iOS App 计划（阶段 1：仅公网 HTTPS）

> 目标：先用 **Capacitor** 把现有 React/Vite 前端做成可安装的 iPhone App（Internal Build），
> **只使用公网域名** `https://papertok.ai`（推荐主域；`https://papertok.net` 可选别名），不做 LAN 直连（避免 ATS/本地网络权限等平台复杂度）。
>
> 关键词：最小成本、最快跑通、工程可持续（版本化、验收、回归、安全边界）。
>
> **当前状态**：✅ 已在本地 Xcode 真机安装运行成功（internal build）。

---

## 0) 范围与非目标

### 0.1 范围（本阶段必须交付）
- iOS 真机可安装运行（internal build）
- 功能闭环：
  - 竖滑 feed（`/api/papers/random`）
  - 详情弹窗：讲解 / 原文（MinerU MD）/ 图片与图注（`/api/papers/{id}` + `/static/*`）
  - 打开 arXiv PDF（外链）
  - 分享当前 paper 链接
- 网络：**只走公网 HTTPS**：`https://papertok.ai`（推荐主域；`https://papertok.net` 可选别名）

### 0.2 非目标（本阶段不做）
- LAN 直连（HTTP/HTTPS）
- 登录/账号体系
- 推送通知
- Admin 内置到 App（默认不提供入口）
- 上架 App Store（可为后续预留路径，但不作为 DoD）

---

## 1) 安全边界（必须遵守）

1) App 只调用 **公开内容面**：
- `/healthz`
- `/api/papers/*`
- `/api/status`（public 摘要）
- `/static/*`

2) App 不调用 / 不暴露：
- `/admin*`
- `/api/admin*`

3) App 侧不保存/不携带任何管理密钥：
- 不存 `PAPERTOK_ADMIN_TOKEN`
- 不发送 `X-Admin-Token`

4) 公网信息泄露基线保持：
- S0 已完成：public `/api/*` 不应泄露 `/Users/...`、`log_path` 等（回归测试：`ops/security_smoke.sh`）

---

## 2) 技术路线

- App 壳：Capacitor（iOS WebView）
- Web 代码：保持现状 React + Vite
- 原生能力（按需引入）：
  - `@capacitor/browser`：打开外链/PDF
  - `@capacitor/share`：系统分享
  - `@capacitor/preferences`：保存少量本地设置（如 debug flags；本阶段可不做）

---

## 3) 工程改造点（为稳定性/可维护性）

### 3.1 单点 API Base（单一事实源）（已落地）

为避免再次出现“部分页面能看、弹窗/图片加载失败”的局部故障，前端已实现单点真理：
- `src/lib/apiBase.ts`：统一导出 `API_BASE` 与 `apiUrl()`
- 关键模块（feed、详情、Admin）均已改为从该模块取 base

本阶段仅公网：`VITE_API_BASE=https://papertok.ai`（见 `.env.capacitor`；若你想用别名也可改成 `https://papertok.net`）。

### 3.2 处理 Service Worker（Capacitor 环境）（已落地）

风险：WebView + SW 可能导致“缓存黏住旧 JS/CSS”，出现 Loading/图片不出等。

当前实现：`vite build --mode capacitor` 时禁用 PWA（见 `vite.config.ts`），从而避免在 Capacitor 环境引入 Service Worker 缓存干扰；Web 端仍保留 PWA。

---

## 4) WBS（里程碑、任务、验收）

### Phase 0 — 前置准备（0.5 天）
**输入确认**：
- iOS Bundle ID（例如 `com.gwaanl.papertok`）
- 是否有 Apple Developer Program：
  - 有：可做 TestFlight（后续）
  - 没有：先 Xcode 直装到你的手机（可行，但证书/安装周期受限）

**DoD**：可以在 Xcode 里跑起一个空壳 App。

### Phase 1 — Capacitor iOS MVP（1–2 天）
任务：
1) 在 `frontend/wikitok/frontend/` 初始化 Capacitor（webDir 指向 `dist`）并提交 `ios/` 工程（便于协作）
2) 构建与同步（仅公网）：
   - `npm run cap:sync:ios`
   - 该脚本会执行 `vite build --mode capacitor`，并读取 `frontend/wikitok/frontend/.env.capacitor` 中的 `VITE_API_BASE=https://papertok.ai`
3) Xcode 打开并在真机运行：
   - `npm run cap:open:ios`
4) 接入 Browser/Share 插件（按需）

备注：Capacitor iOS 默认采用 Swift Package Manager（SPM），不强依赖 Cocoapods（更适合你当前“无开发者账号 + 本机 Xcode 安装”的流程）。

验收（真机）：
- 首屏能加载出卡片（含图片）
- 点开详情弹窗：讲解/原文/图片都可加载
- PDF 外链能打开
- 分享能正常调起

### Phase 2 — 稳定性与可诊断性（1–2 天）
任务：
- 加一个隐藏的“诊断页”（仅 debug build）：
  - 显示当前 base（固定 public）
  - 一键测试 `/healthz`、`/api/status`、`/api/papers/random`
- 前端请求增加合理的超时与错误提示（避免白屏/无限 Loading）

验收：
- 弱网下可给出明确错误（而不是一直转圈）
- 可快速定位是网络问题还是接口问题

### Phase 3 — 交付与版本化（0.5–1 天）
任务：
- 版本号规范：App 版本（CFBundleShortVersionString）与 build number（CFBundleVersion）
- 出一个“内部安装说明”（如何用 Xcode 安装 / 或 TestFlight）

验收：
- 形成可重复的 build 流程（任何人照文档能复现）

---

## 5) 测试矩阵（本阶段）

- 设备：至少 1 台主力 iPhone + 1 台不同 iOS 版本（如可用）
- 网络：Wi‑Fi / 5G / 弱网（限速）
- 场景：
  - 连续滑动 50+ 卡不卡
  - 反复打开/关闭详情弹窗（观察内存与卡顿）
  - 图片加载失败时是否能降级（不阻塞 UI）

---

## 6) 后续（阶段 2：再引入 LAN 直连）

当 iOS MVP 稳定后，再开启 LAN（用于更快的本地测试/更低延迟）：
- LAN HTTP：需要 ATS 例外 + 本地网络权限（更麻烦）
- LAN HTTPS：更正规，但需要证书信任/局域网域名规划

建议：先把 App 体验与工程链路打磨好，再做 LAN。
