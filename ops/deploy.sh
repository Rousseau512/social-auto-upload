#!/bin/bash
# 在跑真号的机器（公司 Mac mini）上部署 fork 的最新代码：拉代码、按锁文件装依赖、补浏览器、冒烟检查。
# 用法：ops/deploy.sh [冒烟用的抖音账号名，默认 test01]
# 在 Herdr 的 pane 里手动运行；不要在发布任务进行中部署。
set -euo pipefail
cd "$(dirname "$0")/.."
account=${1:-test01}

branch=$(git branch --show-current)
if [ "$branch" != main ]; then
  echo "当前不在 main（${branch:-detached HEAD}），回滚过的话先 git checkout main"; exit 1
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "工作区有未提交的改动，先处理再部署："; git status --short --untracked-files=no; exit 1
fi

before=$(git rev-parse --short HEAD)
git pull --ff-only
after=$(git rev-parse --short HEAD)
echo "代码：${before} -> ${after}"

mise trust -q mise.toml >/dev/null 2>&1 || true
uv sync --frozen
.venv/bin/patchright install chromium   # 已装好的版本会直接跳过
chmod 600 cookies/*.json 2>/dev/null || true   # sau 自己登录写出的会话是 644

.venv/bin/sau --help >/dev/null
result=$(.venv/bin/sau douyin check --account "$account" 2>/dev/null | tail -1)
echo "冒烟：sau douyin check --account ${account} -> ${result}"
if [ "$result" != valid ]; then
  echo "冒烟没通过。要回滚：git checkout ${before} && uv sync --frozen（修好后 git checkout main 再部署）"; exit 1
fi
echo "部署完成：${after}。要回滚：git checkout ${before} && uv sync --frozen"
