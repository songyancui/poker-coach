#!/bin/bash
# 把 index.html 打包成安卓 APK。改完 index.html 后运行一次即可。
#   ./build-apk.sh           调试版 → 德州教练.apk（调试签名，自己装着用）
#   ./build-apk.sh release   正式版 → 德州教练-release.apk（正式签名，用于发布）
# 正式签名需要 ~/.android-keys/poker-coach.properties（不在仓库里，见 README）。
# 需要：Node.js、JDK 21、Android SDK。默认路径按 Homebrew 安装，可用环境变量覆盖：
#   JAVA_HOME=/path/to/jdk21 ANDROID_HOME=/path/to/android-sdk ./build-apk.sh
set -euo pipefail
cd "$(dirname "$0")"
export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home}"
export ANDROID_HOME="${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}"
MODE="${1:-debug}"

if [ "$MODE" = "release" ]; then
  PROPS="${POKER_KEYSTORE_PROPS:-$HOME/.android-keys/poker-coach.properties}"
  [ -f "$PROPS" ] || { echo "缺少签名配置 $PROPS，无法打正式版。"; exit 1; }
  TASK=assembleRelease; SRC=app/android/app/build/outputs/apk/release/app-release.apk; OUT="德州教练-release.apk"
else
  TASK=assembleDebug;   SRC=app/android/app/build/outputs/apk/debug/app-debug.apk;     OUT="德州教练.apk"
fi

[ -d app/node_modules ] || (cd app && npm ci)
[ -f app/android/local.properties ] || echo "sdk.dir=$ANDROID_HOME" > app/android/local.properties

mkdir -p app/www
cp index.html app/www/index.html
(cd app && npx cap sync android)
(cd app/android && ./gradlew "$TASK" --console=plain -q)
cp "$SRC" "$OUT"
echo "完成：$(pwd)/$OUT"

# 手机用 USB 连着电脑（已开启 USB 调试）时，自动安装到手机
if "$ANDROID_HOME/platform-tools/adb" get-state >/dev/null 2>&1; then
  "$ANDROID_HOME/platform-tools/adb" install -r "$OUT" && echo "已安装到手机"
fi
