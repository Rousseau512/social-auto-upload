# ops：多账号运营的辅助脚本

这个目录是 fork 之后加的，上游没有。只在跑真号的那台机器（公司 Mac mini）上使用，要在 macOS 图形会话里运行，因为要弹出 Chrome 窗口。

## 账号录入（login/）

`sau douyin login` 只等约 2 分钟，截出来的二维码常常已经过期，所以录入改走下面这条路：用普通 Chrome 让人不限时扫码，再通过调试端口把会话导出成 sau 认的格式。

1. 开窗口：`ops/login/open_windows.sh 5 douyin`（视频号用 `tencent`，小红书用 `xiaohongshu`）。每个窗口用独立的浏览器目录 `browser-profiles/pending-…`，调试端口抖音从 9231、视频号从 9241、小红书从 9251 起；端口被占就跳过，所以想"再开一个"就把数字加一重跑。
2. 扫码：人通过屏幕共享连到 Mac mini，一个窗口登一个号。二维码失效就点刷新，短信或身份验证也在窗口里完成。
3. 导出：`python ops/login/export_douyin.py 5`、`python ops/login/export_tencent.py 4` 或 `python ops/login/export_xiaohongshu.py 3`（后两个可以先加 `--dry` 只看识别结果）。从页面读出抖音号、视频号 ID 或小红书号当账号名，会话写成 `cookies/<平台>_<账号名>.json`（权限 600），并登记到 `cookies/accounts-<平台>.tsv`。
4. 收尾：`ops/login/close_windows.sh douyin`，关掉这些 Chrome（调试端口本机其他用户也能连），并把浏览器目录改名为 `browser-profiles/<平台>_<账号名>`。重新登录的号，旧目录会挪到 `browser-profiles/.replaced/` 留底。这一轮没导出的窗口不改名，目录留在 `pending-…`，没用就删掉。
5. 验证：`sau douyin check --account <账号名>`（小红书是 `sau xiaohongshu check`）。视频号另跑 `python ops/login/verify_tencent.py <账号名>…`，因为 `sau tencent check` 只看页面有没有跳回登录页。

扫完码把窗口关掉也没关系：Chrome 进程和登录态都还在，导出脚本发现没有后台页面时会自己重开一个，并打印一行提示。

## 不进 git 的运行数据

`cookies/`（会话文件和账号表）、`browser-profiles/`、`conf.py` 都只在 Mac mini 本地，被 `.gitignore` 排除。会话文件等于登录凭据，不要拷到别处；仓库是公开的，账号信息也不能提交。

## 部署

代码只在笔记本上改：改完提交、推到 fork（`origin`），再到 Mac mini 的 Herdr pane 里运行 `ops/deploy.sh`。它会检查工作区是否干净，然后 `git pull --ff-only`、`uv sync --frozen`、补装 patchright 的 Chromium、把会话文件权限改成 600，最后用一个抖音号跑 `sau douyin check` 做冒烟。不要在发布任务进行中部署，也不让 Mac mini 定时自动拉代码。

出问题时按脚本最后打印的提示回滚：`git checkout <旧提交> && uv sync --frozen`；修好后先 `git checkout main`，再部署。

跟上游：抖音或视频号改版导致出错时，或者每月一次，在笔记本上 `git fetch upstream && git merge upstream/main`，跑一遍不需要真号的测试，推到 fork 后再部署。我们对上游代码的改动要尽量少、尽量集中，合并时才不容易冲突。

运行环境：Python 由 `mise.toml` 固定为 3.12（上游要求低于 3.13），依赖以 `uv.lock` 为准。上游漏写的 `playwright` 已经补进 `pyproject.toml`，不要再手动 `uv pip install`，否则下次同步会被删掉。
