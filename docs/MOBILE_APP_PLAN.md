# PaperTok 前端做成 iOS/Android App 的工程化计划

> 背景：当前前端是 React + Vite（WikiTok 风格竖滑），后端 FastAPI 同源托管 `dist/`，并且已经接入 PWA（Service Worker）。
>
> 目标：以最小成本把现有前端“产品化”为移动端 App（iOS/Android），同时保持代码复用与可维护性，并为未来上架（TestFlight / App Store / Google Play）留出工程路径。

---

## 0) 已确认的产品决策（来自你当前需求）

- 分发方式：**内部安装**（iOS 走 TestFlight / 内测；Android 直接 APK 或内测渠道）
- 登录：**暂不需要**（未来可能增加账号体系）
- 推送：**不需要**
- 网络：分阶段推进（先快后稳）
  - **阶段 1（当前已决定）**：仅公网 HTTPS（Cloudflare）：`https://papertok.<domain>`
  - **阶段 2（后续可选）**：再加入局域网直连（用于本地测试/更快）：`http://<LAN-IP>:8000` 或局域网域名

> 这会直接影响工程实现：iOS/Android 对“局域网 HTTP”有平台安全策略（ATS / cleartext）需要明确处理，见第 3 章。

---

## 1) 目标与范围

### 1.1 业务目标
- iOS/Android 用户获得“像 App 一样”的体验：
  - 全屏竖滑、启动快、交互稳定
  - 可靠的网络访问（走你的公网域名，例如 Cloudflare Tunnel 的 `https://papertok.<domain>`）
  - 可选：离线浏览已看过内容（弱离线）
  - 可选：分享、打开 PDF、收藏同步

### 1.2 技术目标
- **最大化复用当前 Web 代码**（React/Vite），避免立刻重写为纯原生。
- 构建一条可持续的发布链路（版本号、CI、签名、测试、灰度）。

### 1.3 非目标（短期不做）
- 完整原生重写（React Native/Flutter）
- 复杂的登录/账号体系（除非你明确要）

---

## 2) 方案选型（按成本/收益）

### 方案 A：PWA（最省成本，最快）
**做法**：继续使用当前 PWA，用户通过 Safari/Chrome “添加到主屏幕”。

**优点**：
- 几乎零新工程；iOS/Android 都可用
- 更新无需审核，上线快

**缺点/限制**：
- iOS PWA 仍有限制（后台、推送能力受限；WebKit 限制）
- 无法进入 App Store/Play（除非走包装或特殊政策）

适合：先验证“移动端体验 + 公网访问 + 运营方式”。

### 方案 B：Capacitor（推荐：Web 代码复用 + 可上架）
**做法**：用 Capacitor 把现有 Vite `dist/` 包进 WebView，生成 iOS/Android 原生壳。

**优点**：
- 复用现有前端（成本低）
- 可以上架、可以接入推送/分享/文件等原生能力（通过插件）

**缺点**：
- 仍是 WebView，重度动画/大图场景需要优化

适合：你希望“真的有 iOS/Android App”，且不想重写。

### 方案 C：React Native/Flutter 重写（成本高，性能/原生能力强）
**做法**：重写 UI 层，用 RN/Flutter 调 API。

**优点**：
- 性能与原生体验更可控
- 后续做复杂原生能力更顺

**缺点**：
- 开发成本显著增加；需要重做大量 UI/手势/富文本

适合：产品成熟后、明确需要强原生能力时再做。

> **推荐路径**：A（完善 PWA）→ B（Capacitor internal build，先只用公网 HTTPS 跑通）→（可选）LAN 直连 → 上架准备。

---

## 3) 架构与工程改造点

### 3.1 API Base 统一与环境切换（公网 + 局域网）

**结论：必须做“单点真理”（Single Source of Truth）**，否则很容易出现“主页能看、弹窗/图片加载不了”的局部故障。

当前实现现状：
- 前端已新增单点模块：`src/lib/apiBase.ts`
- Feed / 详情弹窗 / Admin（如启用）都应从该模块获取 `API_BASE` 并用 `apiUrl()` 拼接。

接下来如果要支持 LAN，再在该模块基础上扩展探测/切换逻辑。

建议实现（分两阶段）：

- **阶段 1（当前）仅公网 HTTPS**
  - 使用单一变量：`VITE_API_BASE=https://papertok.<domain>`
  - Capacitor 构建用 `vite build --mode capacitor`，并读取 `.env.capacitor`（仓库已提供）

- **阶段 2（可选）加入 LAN**
  - 在 `src/lib/apiBase.ts` 中加入：LAN/PUBLIC 探测 + 手动覆盖
  - 建议探测点：
    - `GET /healthz`
    - `GET /api/status`（public 摘要）
    - 可选：`GET /api/papers/random`（真实业务）

注意（平台差异）：
- iOS 默认会阻止非 HTTPS（ATS）。如果要用 `http://<LAN-IP>`：
  - 需要在 iOS 工程 Info.plist 配置 ATS 例外（建议只对白名单域名/网段开放，避免全局放开）。
- Android 9+ 默认也会限制明文 HTTP。
  - 需要配置 `networkSecurityConfig` 或 `usesCleartextTraffic`（同样建议仅对 LAN 目标开放）。

替代方案（更“干净”，但成本略高）：
- 在局域网也提供 HTTPS（例如给 Mac mini 加 Caddy + 本地证书，并在手机上信任），这样 App 侧无需 cleartext 例外。

### 3.2 认证与 Admin 的处理
- 普通用户不需要 `/admin`、也不应调用 `/api/admin/*`（这些应被 Cloudflare Access + `X-Admin-Token` 保护）。
- 如果要在 App 中保留 Admin（仅内部运维用途）：
  - 建议只在 debug/internal build 打开入口
  - 交互上走系统浏览器登录 Cloudflare Access（One-time PIN/IdP）
  - API 层仍需 `PAPERTOK_ADMIN_TOKEN`（`X-Admin-Token`）作为第二道门

### 3.3 性能优化（WebView/PWA 共用）
重点风险点：竖滑 + 大图。
- 图片：
  - 服务端已使用带 hash 的文件名（cache bust），可配合长缓存
  - 前端加 `loading=lazy`（已有）
  - 限制一次渲染的卡片数（虚拟列表/回收）
- Markdown/讲解：
  - 详情弹窗按需加载（已有）

### 3.4 离线策略（可选）
- MVP：只缓存静态前端资源（PWA 已有）
- 下一步：缓存最近 N 篇 paper detail（IndexedDB/Cache API）

### 3.5 推送/后台（可选）
- PWA：iOS 受限
- Capacitor：可接 APNS/FCM（需要后端推送服务与 device token 存储）

---

## 4) 里程碑计划（WBS）

### Phase 0 — 需求澄清（完成）
已确认：内部安装、无登录、无推送；**先只用公网 HTTPS 跑通 iOS/Android**，再视需要引入局域网直连。

仍需补充 2 个工程决策（会影响实现复杂度）：
1) 局域网直连你希望用：
   - A) 明文 HTTP（实现快，但需 ATS/cleartext 例外）
   - B) 局域网 HTTPS（更正规，但需要本地证书/信任）
2) iOS 内测分发方式：
   - A) TestFlight（推荐，但需要 Apple Developer Program）
   - B) 仅你自己的手机通过 Xcode 安装（不适合分发给多人）

### Phase 1 — PWA 体验打磨（1-3 天）
目标：不做 App，也能“像 App 一样顺”。
- iOS/Android 真机测试矩阵（Safari/Chrome，低端机）
- 修复：安全区、滚动、手势冲突、图片内存
- Cloudflare 缓存/压缩策略（减轻加载）

验收：
- 从主屏打开，首屏 < 2s（取决于网络）
- 连续滑 50 张不卡死、不崩

### Phase 2 — Capacitor App MVP（2-5 天）
目标：产出可安装的 iOS/Android App（内部签名即可）。
任务：
1) 初始化 Capacitor：
   - `npx cap init`
   - iOS/Android 平台目录
2) Vite build 输出接入 Capacitor
3) App 内配置 `VITE_API_BASE` 指向公网域名
4) 深链路：
   - `/` 与 `/paper/<id>`（如未来要）
5) 基础原生能力：
   - 打开外链/PDF（系统浏览器或内嵌）
   - 分享

验收：
- iOS（真机）可安装运行
- Android（真机）可安装运行
- 可正常拉取 feed、打开详情、看图

### Phase 3 — 上架准备（3-10 天，视需求）
- iOS：Bundle ID、证书、TestFlight、隐私声明
- Android：签名、Play Console、隐私政策
- 崩溃/日志：Sentry（可选）
- CI：GitHub Actions 产物（apk/ipa）

验收：
- TestFlight 可分发
- Play 内测可分发

### Phase 4 — 可选增强（持续迭代）
- 推送：每日 Top10 完成后推送“今日已更新”
- 离线：缓存最近 N 篇
- 账号体系：收藏/阅读进度跨设备同步

---

## 5) 质量与测试计划

### 5.1 测试矩阵
- iOS：Safari（PWA）+ Capacitor WebView
- Android：Chrome（PWA）+ Capacitor WebView
- 网络：
  - 4G/5G
  - 弱网/高延迟

### 5.2 指标
- 首屏时间、滑动掉帧率（主观 + 性能面板）
- 内存占用（是否持续增长）
- 崩溃率（上架后用 Sentry/Crashlytics）

---

## 6) 风险与缓解

1) WebView 性能瓶颈
- 缓解：虚拟列表/回收；图片尺寸控制；避免一次渲染过多 DOM

2) iOS PWA/缓存策略复杂
- 缓解：优先走 Capacitor；或在 PWA 上减少 SW 侵入

3) 安全（Admin 暴露）
- 缓解：App 不内置 Admin；或 Access + token 双重保护

---

## 7) 我需要你回答的 4 个问题（用于把计划变成实施）

1) 你希望最终“上架到 App Store/Google Play”，还是只要内部安装（TestFlight/企业签名/Android APK）？
2) App 是否需要登录/账号？还是匿名即可？
3) 是否需要推送（每天 Top10 更新提醒）？
4) 你希望 App 访问的是公网域名（Cloudflare）为主，还是也要支持局域网直连 Mac（例如在家里更快）？
