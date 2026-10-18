"""扫描 9231 起的调试端口，把已登录抖音创作者中心的窗口导出成 sau 会话。

会话存为 cookies/douyin_<抖音号>.json（权限 600），并追加到 cookies/accounts-douyin.tsv。
只断开调试连接，不关浏览器。用法：python ops/login/export_douyin.py [N]
"""
import asyncio
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

from patchright.async_api import async_playwright

os.chdir(Path(__file__).resolve().parents[2])
BASE_PORT = 9230
REGISTRY = "cookies/accounts-douyin.tsv"
INFO_JS = "fetch('/web/api/media/user/info/', {credentials: 'include'}).then(r => r.json())"


def cdp_alive(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
        return True
    except Exception:
        return False


async def export_port(p, port):
    if not cdp_alive(port):
        return None
    browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    ctx = browser.contexts[0]
    page = next((pg for pg in ctx.pages if "creator.douyin.com" in pg.url), None)
    if page is None:
        return {"port": port, "status": "没有创作者中心页面"}
    cookies = await ctx.cookies()
    if not any(c["name"] == "sessionid" and c["value"] for c in cookies):
        return {"port": port, "status": "未登录"}
    try:
        data = await page.evaluate(INFO_JS)
    except Exception as e:
        data = {"error": str(e)[:120]}
    user = data.get("user") or {}
    unique_id = user.get("unique_id") or user.get("short_id") or ""
    uid = str(user.get("uid") or "")
    nickname = user.get("nickname") or ""
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", str(unique_id or uid)) or f"port{port}"
    out = f"cookies/douyin_{key}.json"
    await ctx.storage_state(path=out)
    os.chmod(out, 0o600)
    if not user:
        print(f"[{port}] 用户信息接口返回结构未识别：{json.dumps(data, ensure_ascii=False)[:300]}")
    return {"port": port, "status": "已导出", "account": key, "nickname": nickname,
            "unique_id": unique_id, "uid": uid, "file": out}


async def main(n):
    rows = []
    async with async_playwright() as p:
        for i in range(1, n + 1):
            try:
                r = await export_port(p, BASE_PORT + i)
            except Exception as e:
                # 窗口被关掉、只剩进程的 Chrome 连上去会报 "Browser context management is not supported"，
                # 先用 curl -X PUT "http://127.0.0.1:<端口>/json/new?https://creator.douyin.com/" 重开页面
                r = {"port": BASE_PORT + i, "status": f"出错：{str(e)[:150]}"}
            if r:
                rows.append(r)
    new = [r for r in rows if r["status"] == "已导出"]
    if new:
        exists = os.path.exists(REGISTRY)
        with open(REGISTRY, "a") as f:
            if not exists:
                f.write("account\tnickname\tunique_id\tuid\texported_at\tport\n")
            for r in new:
                f.write(f"{r['account']}\t{r['nickname']}\t{r['unique_id']}\t{r['uid']}\t"
                        f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{r['port']}\n")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    if not rows:
        print("没有找到打开的登录窗口")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 5))
