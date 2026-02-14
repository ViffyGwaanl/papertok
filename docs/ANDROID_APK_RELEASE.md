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
应能看到类似 `17.x`。

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

---

## 6) 推荐分发方式：GitHub Releases

这样做的好处：
- 可追溯（每次发包一个 tag）
- 可写 release notes
- 可附带 sha256 校验

### 6.1 时间戳 release（审计用，推荐）

推荐 tag 格式：
- `android-YYYYMMDD-HHMMSS`

例如：`android-20260211-105244`

创建 release 并上传资源（建议 prerelease，因为是 internal build）：

```bash
cd /path/to/papertok

TAG="android-YYYYMMDD-HHMMSS"
APK="papertok/exports/android/<your>.apk"
SHA="${APK}.sha256"

gh release create "$TAG" \
  --repo ViffyGwaanl/papertok \
  --title "PaperTok Android APK ($TAG)" \
  --notes "Internal build." \
  --prerelease \
  "$APK" "$SHA"
```

### 6.2 一个“永远最新”的 stable 下载链接（强烈推荐）

为了让 README、群公告等永远指向最新 APK，可以维护一个非 prerelease 的 moving tag：`android-latest`，并上传固定文件名资产：
- `papertok-android-latest.apk`
- `papertok-android-latest.apk.sha256`

这样下载链接可以固定为：
- `https://github.com/ViffyGwaanl/papertok/releases/latest/download/papertok-android-latest.apk`

更新方式（复用同一个 release，不改链接）：

```bash
TAG="android-latest"
APK_SRC="papertok/exports/android/<your>.apk"
SHA_SRC="${APK_SRC}.sha256"

# 1) 确保 release 存在（非 prerelease）
# 如已存在可跳过
# gh release create "$TAG" --repo ViffyGwaanl/papertok --title "PaperTok Android (latest)" --notes "Moving tag for internal distribution."

# 2) 上传固定文件名（--clobber 覆盖同名资产）
cp "$APK_SRC" /tmp/papertok-android-latest.apk
cp "$SHA_SRC" /tmp/papertok-android-latest.apk.sha256

gh release upload "$TAG" \
  --repo ViffyGwaanl/papertok \
  --clobber \
  /tmp/papertok-android-latest.apk \
  /tmp/papertok-android-latest.apk.sha256
```

---

## 7) iCloud/互传目录的坑（重要）

在 macOS 上，如果你把待上传 APK 放在 iCloud Drive（例如：
`~/Library/Mobile Documents/com~apple~CloudDocs/互传`），在某些自动化/后台上下文里读取会失败：
- `OSError: [Errno 11] Resource deadlock avoided`

**规避方式**：发布前先把 APK 拷贝到一个非 iCloud 的本地目录（例如 `/tmp/` 或 `~/Downloads/`），再执行 `gh release upload`。

---

## 8) 每次发新版本：记得 bump versionCode

文件（优先看 kts）：
- `papertok/frontend/wikitok/frontend/android/app/build.gradle.kts`（或旧版 `build.gradle`）

规则：
- **每次发布新 APK 必须把 `versionCode` +1**（否则对方无法“覆盖安装更新”）
- `versionName` 是给人看的版本号（建议一起改）

---

## 9) 安装侧注意事项（给收包的人）

- 首次安装：需要允许“安装未知来源应用”。
- 如果对方之前装过你用**不同签名**打的包（比如 debug 版），会提示签名不一致：
  - 解决：卸载旧包再安装新包。

---

## 10) 可选：更推荐 Play 分发时用 AAB

如果未来要上 Google Play，推荐产物是 AAB：

```bash
cd papertok/frontend/wikitok/frontend/android
./gradlew bundleRelease
```

但给人直接安装时，APK 更方便。
