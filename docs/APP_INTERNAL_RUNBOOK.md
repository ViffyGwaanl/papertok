# PaperTok App Internal Runbook（iOS/Android 本地安装指南）

> 目的：你在自己的开发机上把仓库 clone 下来后，能稳定复现 iOS/Android 的安装与运行。
>
> 当前阶段：**仅公网 HTTPS**（推荐 `https://papertok.ai`；`https://papertok.net` 可选别名），不包含 LAN 直连。

---

## 1) 通用准备

- Node/npm 可用
- Android：Android Studio + SDK
- iOS：Xcode

仓库：`https://github.com/ViffyGwaanl/papertok`（private）

前端目录：
```bash
cd papertok/frontend/wikitok/frontend
```

安装依赖：
```bash
npm install
```

构建并同步原生工程（仅公网）：
```bash
npm run cap:sync:ios
npm run cap:sync:android
```

---

## 2) iOS（无开发者账号：Xcode 直装到自己的 iPhone）

> 限制：Personal Team 通常 7 天签名过期；到期后重新 Run 一次即可。

步骤：
1) 用数据线连接 iPhone
2) iPhone 打开开发者模式（iOS 16+）并信任该电脑
3) 打开 Xcode：
```bash
npm run cap:open:ios
```
4) Xcode → Signing & Capabilities：
- Team 选择你的 Apple ID（Personal Team）
- 如果 Bundle ID 冲突，改成 `com.gwaanl.papertok.ios`
5) 选择设备 → Run ▶

---

## 3) Android（Android Studio Run）

步骤：

### 3.1 首次安装 Android SDK（只需一次）
1) Android Studio 弹窗提示 `Select SDKs` / `SDK Manager` 时：安装/勾选
- Android SDK Platform：建议 Android 14（API 34）（可选再加 Android 13 / API 33）
- Android SDK Build-Tools：34.x
- Android SDK Platform-Tools（包含 `adb`，必装）
- Android SDK Command-line Tools (latest)（推荐）

2) 若遇到 `adb: command not found`：
- 临时用完整路径（默认位置）：
  - `~/Library/Android/sdk/platform-tools/adb devices`
- 或永久加入 PATH（`~/.zshrc`）：
  - `export PATH="$HOME/Library/Android/sdk/platform-tools:$PATH"`

> 说明：你的 SDK 实际路径以 Android Studio 的 **Android SDK Location** 为准。

### 3.2 导入工程并运行
1) 手机打开 Developer options + USB debugging
2) 打开 Android Studio：
```bash
npm run cap:open:android
```
3) 第一次导入工程时，`Importing 'android' Gradle Project` 可能需要 10–30 分钟（下载 Gradle/依赖属正常）。
4) 选择设备 → Run ▶

---

## 4) 常见问题（Troubleshooting）

### 4.1 App 打开后加载失败（白屏/一直 Loading）
- 确认公网可访问：
  - `https://papertok.ai/healthz`
  - `https://papertok.ai/api/status`
  - （可选别名）`https://papertok.net/healthz`
  - （可选别名）`https://papertok.net/api/status`
- 确认 Capacitor build 使用了 `.env.capacitor`：
  - `VITE_API_BASE=https://papertok.ai`（推荐；或用别名 `https://papertok.net`）

### 4.2 iOS 签名问题
- 确认 Xcode 已登录 Apple ID
- 重新选择 Team
- 检查 iPhone 是否启用开发者模式

### 4.3 Android Gradle/SDK 问题
- 用 Android Studio 的 SDK Manager 补齐组件（至少：API 34 Platform + Build-Tools + Platform-Tools）
- 第一次 `Importing 'android' Gradle Project` / Gradle Sync 很慢属正常（下载依赖）

### 4.4 `adb` 找不到
- 先确认已安装：Android SDK Platform-Tools
- 默认位置：`~/Library/Android/sdk/platform-tools/adb`
- 终端临时验证：
  - `~/Library/Android/sdk/platform-tools/adb devices`
- 永久加入 PATH：把下面加入 `~/.zshrc`
  - `export PATH="$HOME/Library/Android/sdk/platform-tools:$PATH"`
