"""扫描 9241 起的调试端口，把已登录视频号助手的窗口导出成 sau 会话。

会话存为 cookies/tencent_<视频号ID>.json（权限 600），并追加到 cookies/accounts-tencent.tsv。
视频号的登录态有一部分在 localStorage，经调试端口导出时 storage_state 拿不到，这里从页面补写。
只断开调试连接，不关浏览器。用法：python ops/login/export_tencent.py [N] [--dry]（--dry 只识别不写文件）
"""
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from patchright.async_api import async_playwright

os.chdir(Path(__file__).resolve().parents[2])
BASE_PORT = 9240
REGISTRY = "cookies/accounts-tencent.tsv"
AUTH_JS = """async () => {
  const r = await fetch('/cgi-bin/mmfinderassistant-bin/auth/auth_data', {
    method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({timestamp: String(Date.now()), _log_finder_uin: '', _log_finder_id: '',
                          rawKeyBuff: null, pluginSessionId: null, scene: 7, reqScene: 7})});
  return await r.json();
}"""
LS_JS = "() => Object.entries(localStorage)"


def finder_user(data):
    """auth_data 返回里的本号信息：nickname、uniqId（sph 开头的视频号 ID）、finderUsername。"""
    if not isinstance(data, dict):
        return {}
    return (data.get("data") or {}).get("finderUser") or {}


async def export_port(p, port, dry):
    browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    ctx = browser.contexts[0]
    page = next((pg for pg in ctx.pages if "channels.weixin.qq.com" in pg.url), None)
    if page is None:
        return {"port": port, "status": "没有视频号助手页面"}
    if "login.html" in page.url or any("qrconnect" in f.url for f in page.frames):
        return {"port": port, "status": "未登录", "url": page.url}
    try:
        data = await page.evaluate(AUTH_JS)
    except Exception as e:
        data = {"error": str(e)[:150]}
    fu = finder_user(data)
    nickname = fu.get("nickname", "")
    uniq_id = fu.get("uniqId", "")
    finder_username = fu.get("finderUsername", "")
    if not fu:
        text = await page.evaluate("() => document.body.innerText.slice(0, 300)")
        print(f"[{port}] auth_data 未识别：{json.dumps(data, ensure_ascii=False)[:300]}")
        print(f"[{port}] 页面文字：{text!r}")
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", uniq_id or finder_username) or f"port{port}"
    r = {"port": port, "status": "已识别" if dry else "已导出", "account": key, "nickname": nickname,
         "uniq_id": uniq_id, "finder_username": finder_username, "url": page.url}
    if dry:
        return r
    out = f"cookies/tencent_{key}.json"
    await ctx.storage_state(path=out)
    state = json.load(open(out))
    if not state.get("origins"):
        items = await page.evaluate(LS_JS)
        if items:
            origin = re.match(r"https://[^/]+", page.url).group(0)
            state["origins"] = [{"origin": origin, "localStorage": [{"name": k, "value": v} for k, v in items]}]
            json.dump(state, open(out, "w"), ensure_ascii=False)
    os.chmod(out, 0o600)
    r["file"] = out
    r["cookies"] = len(state["cookies"])
    r["localStorage"] = sum(len(o.get("localStorage", [])) for o in state.get("origins", []))
    return r


async def main(n, dry):
    rows = []
    async with async_playwright() as p:
        for i in range(1, n + 1):
            try:
                r = await export_port(p, BASE_PORT + i, dry)
            except Exception as e:
                r = {"port": BASE_PORT + i, "status": f"出错：{str(e)[:150]}"}
            rows.append(r)
    new = [r for r in rows if r["status"] == "已导出"]
    if new:
        exists = os.path.exists(REGISTRY)
        with open(REGISTRY, "a") as f:
            if not exists:
                f.write("account\tnickname\tuniq_id\tfinder_username\texported_at\tport\n")
            for r in new:
                f.write(f"{r['account']}\t{r['nickname']}\t{r['uniq_id']}\t{r['finder_username']}\t"
                        f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{r['port']}\n")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(int(args[0]) if args else 4, "--dry" in sys.argv))
