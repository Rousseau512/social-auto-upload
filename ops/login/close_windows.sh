#!/bin/bash
# 关掉某个平台 pending-* 登录窗口的 Chrome，并按账号表里的端口把浏览器目录改名为 <平台>_<账号>。
# 用法：ops/login/close_windows.sh [douyin|tencent]（先跑完导出再关）
set -uo pipefail
cd "$(dirname "$0")/../.."
platform=${1:-douyin}
case "$platform" in
  douyin|tencent) registry="cookies/accounts-${platform}.tsv"; prefix="pending-${platform}-" ;;
  *) echo "未知平台：$platform"; exit 2 ;;
esac
map=$(ps -axo command= | grep -E "Google Chrome --user-data-dir=.*/browser-profiles/${prefix}" | grep -v grep \
  | sed -E 's/.*--user-data-dir=([^ ]+) --remote-debugging-port=([0-9]+).*/\2 \1/' | sort -u)
echo "$map"
while read -r port dir; do [ -n "$port" ] && pkill -TERM -f "Google Chrome --user-data-dir=${dir} "; done <<< "$map"
for t in $(seq 1 10); do
  ps -axo command= | grep -E "browser-profiles/${prefix}" | grep -v grep >/dev/null || break; sleep 1
done
ps -axo command= | grep -E "browser-profiles/${prefix}" | grep -v grep >/dev/null && { echo "还有 Chrome 没退出"; exit 1; }
while read -r port dir; do
  [ -n "$port" ] || continue
  acct=$(awk -F'\t' -v p="$port" 'NR>1 && $6==p {a=$1} END{print a}' "$registry" 2>/dev/null)
  if [ -n "$acct" ]; then
    target="browser-profiles/${platform}_${acct}"
    if [ -e "$target" ]; then
      # 重新登录的号：旧目录挪到 .replaced/ 留底，换上这次登录的目录
      mkdir -p browser-profiles/.replaced
      mv "$target" "browser-profiles/.replaced/${platform}_${acct}-$(date +%Y%m%d%H%M%S)"
    fi
    mv "$dir" "$target" && echo "$port -> $target"
  else
    echo "$port 未改名（acct=$acct）"
  fi
done <<< "$map"
