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

## 2) 仓库结构建议（最小改动）

在 `papertok/frontend/wikitok/frontend/` 下新增 `capacitor/`（或直接在该目录初始化 Capacitor）。

理由：
- Vite build 产物已经在这里（dist）
- Capacitor 默认就以 web assets 为输入

---

## 3) API Base（公网 + LAN）实现建议

### 3.1 前端环境变量
新增：
- `VITE_API_BASE_PUBLIC`（必填）：`https://papertok.<domain>`
- `VITE_API_BASE_LAN`（可选）：`http://<LAN-IP>:8000` 或 `http://papertok.lan:8000`

并在代码中实现：
- 并发探测：
  - `GET /healthz`
  - `GET /api/status`（public 摘要；避免“健康但业务不可用”误判）
- 优先 LAN，失败再 fallback 到 PUBLIC
- 支持手动覆盖（Preferences/localStorage）

### 3.2 iOS/Android 明文 HTTP 的合规处理（如果选 HTTP 直连）

iOS（ATS）：
- 方案 1（快但粗）：`NSAllowsArbitraryLoads=true`（不推荐长期）
- 方案 2（推荐）：只为特定域名/子域开例外（例如 `papertok.lan`）

Android：
- 建议通过 `networkSecurityConfig` 只对 LAN domain 允许 cleartext。

> 更正规方案：局域网也用 HTTPS（需要你为局域网域名签证书并在手机信任）。

---

## 4) Capacitor MVP 实施步骤（概要）

> 具体命令会在你确定 iOS/Android 的包名、以及 LAN 访问策略后补齐。

1) 初始化 Capacitor
- `npm i -D @capacitor/core @capacitor/cli`
- `npx cap init`（设置 appName / appId）

2) 添加平台
- `npm i -D @capacitor/ios @capacitor/android`
- `npx cap add ios`
- `npx cap add android`

3) 连接 Vite build 输出
- Capacitor 配置 `webDir=dist`

4) Build + Sync
- `npm run build`
- `npx cap sync`

5) 真机运行
- iOS：`npx cap open ios`（Xcode 运行）
- Android：`npx cap open android`（Android Studio 运行）

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
