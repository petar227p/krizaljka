#!/bin/bash
# Builds a debug APK with the current player and puzzle data baked in.
# Re-run this after fetching new puzzles so the APK has them.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
ASSETS="$HERE/app/src/main/assets"

export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools

# Copy the player and the downloaded data into the app's assets.
rm -rf "$ASSETS"
mkdir -p "$ASSETS/data"
cp "$REPO/index.html" "$ASSETS/index.html"
cp -R "$REPO/data/." "$ASSETS/data/"

cd "$HERE"
./gradlew assembleDebug

APK="$HERE/app/build/outputs/apk/debug/app-debug.apk"
echo "Built: $APK"
