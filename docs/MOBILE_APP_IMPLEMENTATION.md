# PaperTok iOS/Android App（Internal Build）实施方案

> 这是在 `docs/MOBILE_APP_PLAN.md` 基础上的“落地版”：偏命令级与工程结构。
>
> 当前前提：
> - 内部安装（不上架）
> - 暂不需要登录、推送
> - **阶段 1：仅公网 HTTPS（先跑通 iOS/Android MVP）**
> - 后续阶段再引入局域网直连（用于本地测试）

---

## 1) 推荐技术栈

- Web：保持 React + Vite（现状）
- App 壳：**Capacitor**（iOS/Android WebView）
- 原生能力（按需）：
  - 打开外部链接：Capacitor Browser
  - 分享：Capacitor Share
  - 本地存储：Capacitor Preferences

---

## 2) 仓库结构（已落地）

Capacitor 工程已直接初始化在 `papertok/frontend/wikitok/frontend/`，并提交原生工程目录：
- `ios/`
- `android/`

理由：
- Vite build 产物已经在这里（dist）
- Capacitor 默认就以 web assets 为输入

---

## 3) API Base（单点真理，阶段 1：仅公网 HTTPS）

### 3.1 单点真理模块（已落地）
- `src/lib/apiBase.ts`：前端唯一的 `API_BASE` 来源（Single Source of Truth）
- `apiUrl('/api/...')` / `assetUrl('/static/...')`：统一拼接路径

### 3.2 阶段 1（当前）：仅公网 HTTPS
- 使用单一变量：`VITE_API_BASE=https://papertok.<domain>`
- 仓库已提供：`frontend/wikitok/frontend/.env.capacitor`（Capacitor 构建时读取）

> 备注：Capacitor WebView 的 origin 通常是 `capacitor://localhost`，因此必须显式配置 `VITE_API_BASE`。

### 3.3 阶段 2（可选）：加入 LAN
后续如果要 LAN 直连，再在 `apiBase.ts` 上扩展：
- LAN/PUBLIC 探测（healthz + public /api/status + 可选 /api/papers/random）
- 手动覆盖（Preferences/localStorage）
- iOS ATS / Android cleartext 合规配置

### 3.2 iOS/Android 明文 HTTP 的合规处理（如果选 HTTP 直连）

iOS（ATS）：
- 方案 1（快但粗）：`NSAllowsArbitraryLoads=true`（不推荐长期）
- 方案 2（推荐）：只为特定域名/子域开例外（例如 `papertok.lan`）

Android：
- 建议通过 `networkSecurityConfig` 只对 LAN domain 允许 cleartext。

> 更正规方案：局域网也用 HTTPS（需要你为局域网域名签证书并在手机信任）。

---

## 4) Capacitor MVP 实施步骤（概要）

> 现状：iOS/Android 工程已在远程机器生成并提交到仓库，便于你在本地直接用 Xcode / Android Studio 安装到真机。

1) 安装依赖
- `npm i -D @capacitor/core @capacitor/cli @capacitor/ios @capacitor/android`

2) 统一构建（仅公网 HTTPS）
- `npm run build:capacitor`（内部会执行 `vite build --mode capacitor`，读取 `.env.capacitor`）

3) Sync
- iOS：`npm run cap:sync:ios`
- Android：`npm run cap:sync:android`

4) 打开原生工程
- iOS：`npm run cap:open:ios`
- Android：`npm run cap:open:android`

5) 真机运行
- Xcode / Android Studio 选择设备 → Run ▶

---

## 5) 内部分发（Internal Distribution）

### 5.1 Android
- 产出：debug APK（最快）或 release APK（更像生产）
- 分发：直接发文件安装；或 Google Play 内测（可选）

### 5.2 iOS
- TestFlight（推荐）：需要 Apple Developer Program
- 若没有：
  - 只能通过 Xcode 在你的设备上安装/运行（不适合多人内测）

---

## 6) 验收清单（Internal MVP）

- [ ] iOS：可安装启动，能加载 feed、打开详情、查看图片与 PDF 链接
- [ ] Android：同上
- [ ] 网络：在家局域网优先走 LAN；外出走公网域名
- [ ] `/admin` 不在 App 内暴露（或仅 debug/internal build 可见，且必须走 Cloudflare Access + `X-Admin-Token`）

---

## 7) 你需要最终确认的 3 个输入

1) App 的包名/标识：
- iOS/Android 统一：例如 `ai.papertok.app`（你给一个偏好）

2) 局域网访问策略（二选一）：
- A) 允许 HTTP（我会配置 ATS/cleartext 例外）
- B) 局域网也用 HTTPS（你愿意在手机上安装信任证书）

3) iOS 是否有 Apple Developer Program（年费）？
- 有：走 TestFlight
- 没有：只能先 Xcode 本机安装
