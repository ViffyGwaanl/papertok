# PaperTok Android App 计划（阶段 1：仅公网 HTTPS）

> 目标：用 **Capacitor** 把现有 React/Vite 前端打包成 Android App（Internal Build），
> **只使用公网域名** `https://papertok.app-so.com`，不做 LAN 直连（避免 Android cleartext/networkSecurityConfig 复杂度）。

---

## 0) 范围与非目标

### 0.1 范围（本阶段必须交付）
- Android 真机可安装运行（debug APK / Android Studio Run）
- 功能闭环：
  - 竖滑 feed（`/api/papers/random`）
  - 详情弹窗：讲解 / 原文（MinerU MD）/ 图片与图注（`/api/papers/{id}` + `/static/*`）
  - 打开 arXiv PDF（外链）
  - 分享 paper 链接
- 网络：**只走公网 HTTPS**：`https://papertok.app-so.com`

### 0.2 非目标（本阶段不做）
- LAN 直连（HTTP/HTTPS）
- 登录/账号体系、推送通知
- App 内置 Admin（默认不提供入口）
- 上架 Google Play（后续阶段再做）

---

## 1) 安全边界（必须遵守）

1) App 只调用公开内容面：
- `/healthz`
- `/api/papers/*`
- `/api/status`（public 摘要）
- `/static/*`

2) App 不调用 / 不暴露：
- `/admin*`
- `/api/admin*`

3) App 不保存/不携带任何管理密钥：
- 不存 `PAPERTOK_ADMIN_TOKEN`
- 不发送 `X-Admin-Token`

4) S0 安全回归：
- 上线/改动后必跑 `papertok/ops/security_smoke.sh`

---

## 2) 工程实现（本阶段已采用的约定）

- Capacitor 项目目录：`papertok/frontend/wikitok/frontend/`
- Android 工程目录（提交到 git，便于协作）：`papertok/frontend/wikitok/frontend/android/`
- 构建模式：`vite build --mode capacitor`
- 公网 API base：读取 `frontend/wikitok/frontend/.env.capacitor`：
  - `VITE_API_BASE=https://papertok.app-so.com`

脚本：
- `npm run cap:sync:android`：构建 + `cap sync android`
- `npm run cap:open:android`：用 Android Studio 打开工程

---

## 3) 安装与运行（在你的本地开发机上）

前置：Android Studio + SDK + 一台开启开发者模式的 Android 手机。

```bash
git clone https://github.com/ViffyGwaanl/papertok.git
cd papertok/frontend/wikitok/frontend

npm install
npm run cap:sync:android
npm run cap:open:android
```

在 Android Studio：选择设备 → Run ▶。

---

## 4) 验收清单（Internal MVP）

- [ ] App 启动后可以加载 feed（含图片）
- [ ] 打开详情弹窗：讲解/原文/图片都可加载
- [ ] PDF 外链可以打开
- [ ] 分享可调起
- [ ] App 不包含 Admin 入口

---

## 5) 后续阶段（引入 LAN 直连）

当公网版本稳定后，再引入 LAN：
- Android 需要配置 `networkSecurityConfig` 或 `usesCleartextTraffic`（如果走 HTTP）
- 或改为 LAN HTTPS（更正规）

建议：先把 App 工程链路与体验打磨稳定，再做 LAN。
