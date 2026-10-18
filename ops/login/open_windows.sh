#!/bin/bash
# 同时打开 N 个创作者后台登录窗口：每个窗口用独立浏览器目录和独立调试端口，层叠摆放；端口被占就跳过。
# 用法：ops/login/open_windows.sh [N] [douyin|tencent]
#   douyin：抖音创作者中心，端口 9231 起；tencent：视频号助手，端口 9241 起
set -euo pipefail
cd "$(dirname "$0")/../.."
n=${1:-5}; platform=${2:-douyin}
case "$platform" in
  douyin)  base=9230; url="https://creator.douyin.com/" ;;
  tencent) base=9240; url="https://channels.weixin.qq.com/login.html" ;;
  *) echo "未知平台：$platform"; exit 2 ;;
esac
stamp=$(date +%Y%m%d%H%M%S)
for i in $(seq 1 "$n"); do
  port=$((base + i))
  if curl -s -m 1 "http://127.0.0.1:${port}/json/version" >/dev/null; then echo "端口 ${port} 已被占用，跳过"; continue; fi
  dir="$PWD/browser-profiles/pending-${platform}-${stamp}-${i}"
  mkdir -p "$dir"
  x=$((40 + (i - 1) * 140)); y=$((30 + (i - 1) * 50))
  open -na "Google Chrome" --args --user-data-dir="$dir" --remote-debugging-port="$port" \
    --no-first-run --no-default-browser-check --window-position="$x,$y" --window-size=1100,800 \
    "$url"
  echo "窗口 ${i}：端口 ${port}，目录 ${dir}"
  sleep 1
done
