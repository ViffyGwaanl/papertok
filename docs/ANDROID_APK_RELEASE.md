# Android APK 发布（给别人安装）

> 目标：把 PaperTok Android（Capacitor）打成 **可分发、可升级覆盖安装** 的 APK。
>
> 结论：必须生成 **release + 签名** 的 APK（debug APK 不适合长期分发）。

---

## 1) 为什么必须 Release 签名 APK

- Android “升级覆盖安装”要求：
  1) **applicationId 相同**（本项目：`com.gwaanl.papertok`）
  2) **签名证书相同**（同一个 keystore + alias）
  3) **versionCode 递增**（每次发新包必须 +1）

只要 keystore 丢失，就无法用同一个包名继续升级，只能换包名重新装。

---

## 2) 一次性配置：创建 keystore（只做一次）

在你自己的安全目录（不要放进仓库）创建：

```bash
keytool -genkeypair -v \
  -keystore papertok-release.keystore \
  -alias papertok \
  -keyalg RSA -keysize 2048 -validity 10000
```

把 `papertok-release.keystore` 备份好（例如 iCloud Drive/1Password/加密 U 盘）。

---

## 3) 一次性配置：提供签名参数给 Gradle（推荐写到本机）

把下面内容写入：`~/.gradle/gradle.properties`（没有就创建）

```properties
PAPERTOK_STORE_FILE=/绝对路径/papertok-release.keystore
PAPERTOK_STORE_PASSWORD=你的store密码
PAPERTOK_KEY_ALIAS=papertok
PAPERTOK_KEY_PASSWORD=你的key密码
```

> 说明：该文件在你的机器上，不会进入 git。

---

## 4) 环境要求（Gradle/JDK）

- 需要可用的 Java/JDK（建议 JDK 17）
- 需要 Android SDK/Build-Tools（你已经能用 Android Studio Run 的话通常都齐了）

验证：
```bash
java -version
```
应能看到类似 `17.x`，而不是 “Unable to locate a Java Runtime”。

---

## 5) 每次发包：一条命令（产出 APK）

在仓库根目录执行：

```bash
cd papertok
bash ops/build_android_release_apk.sh
```

输出：
- `papertok/exports/android/*.apk`
- `papertok/exports/android/*.sha256`

你可以直接把 APK 发给别人安装；更推荐的“可追溯分发方式”是发布到 GitHub Releases（见下一节）。

---

## 6) 推荐分发方式：发布到 GitHub Releases

这样做的好处：
- 有固定下载链接，避免聊天记录翻找
- 可写 release notes（版本、变更点、已知问题）
- 可附带 sha256 校验，收包的人能验证文件未被篡改

### 6.1 选择 tag 命名

推荐格式（时间戳为主，简单稳定）：
- `android-YYYYMMDD-HHMMSS`

例如：`android-20260208-040411`

### 6.2 用 `gh` 创建 Release 并上传 APK

前提：你已登录 GitHub CLI：
```bash
gh auth status
```

然后在项目仓库根目录执行（把文件名换成你实际的 APK 路径）：

```bash
cd /path/to/papertok

TAG="android-20260208-040411"
APK="papertok/exports/android/<your>.apk"
SHA="${APK}.sha256"

# 创建 release 并上传资源（建议 prerelease，因为是 internal build）
gh release create "$TAG" \
  --repo ViffyGwaanl/papertok \
  --title "PaperTok Android APK ($TAG)" \
  --notes "Internal build. See docs/ANDROID_APK_RELEASE.md for build/signing." \
  --prerelease \
  "$APK" "$SHA"
```

发布后，把 Release 页面链接发给对方即可。

### 6.3 收包的人如何校验 sha256（可选但推荐）

macOS/Linux：
```bash
shasum -a 256 <apk-file>
```

Windows（PowerShell）：
```powershell
Get-FileHash .\app.apk -Algorithm SHA256
```

与 `.sha256` 文件里的值一致即可。

---

## 7) 每次发新版本：记得 bump versionCode

文件：`papertok/frontend/wikitok/frontend/android/app/build.gradle`

```gradle
versionCode 1
versionName "1.0"
```

规则：
- **每次发布新 APK 必须把 `versionCode` +1**（否则对方无法“覆盖安装更新”）
- `versionName` 是给人看的版本号（建议一起改，比如 1.0 → 1.0.1）

---

## 8) 安装侧注意事项（给收包的人）

- 首次安装：需要允许“安装未知来源应用”（从微信/浏览器/文件管理器安装时系统会提示）。
- 如果对方之前装过你用**不同签名**打的包（比如 debug 版），会提示签名不一致：
  - 解决：卸载旧包再安装新包。

---

## 9) 可选：更推荐 Play 分发时用 AAB

如果未来要上 Google Play，推荐产物是 AAB：

```bash
cd papertok/frontend/wikitok/frontend/android
./gradlew bundleRelease
```

但给人直接安装时，APK 更方便。
