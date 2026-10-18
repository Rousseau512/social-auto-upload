"""扫描 9251 起的调试端口，把已登录小红书创作服务平台的窗口导出成 sau 会话。

会话存为 cookies/xiaohongshu_<小红书号>.json（权限 600），并追加到 cookies/accounts-xiaohongshu.tsv。
窗口被关掉、只剩 Chrome 进程时，会先重开创作服务平台再导出。只断开调试连接，不关浏览器。
用法：python ops/login/export_xiaohongshu.py [N] [--dry]（--dry 只识别不写文件）
"""
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from patchright.async_api import async_playwright

from cdp_util import cdp_alive, ensure_page

os.chdir(Path(__file__).resolve().parents[2])
BASE_PORT = 9250
REGISTRY = "cookies/accounts-xiaohongshu.tsv"
# 创作服务平台自己用的两个接口，哪个能用取哪个；都不行再从页面文字里找"小红书账号"
INFO_JS = """async () => {
  const out = {};
  for (const path of ['/api/galaxy/user/info', '/api/galaxy/creator/home/personal_info']) {
    try { out[path] = await (await fetch(path, {credentials: 'include'})).json(); }
    catch (e) { out[path] = {error: String(e)}; }
  }
  out.text = document.body.innerText.slice(0, 2000);
  return out;
}"""
LS_JS = "() => Object.entries(localStorage)"


FIELDS = {"red_id": ("redId", "red_id", "red_num"), "user_id": ("userId", "user_id"),
          "nickname": ("userName", "nickname", "name")}


def user_info(raw):
    """从两个接口和页面文字里拼出 red_id（小红书号）、user_id、nickname，取不到的留空。"""
    info = dict.fromkeys(FIELDS, "")
    for path in ("/api/galaxy/user/info", "/api/galaxy/creator/home/personal_info"):
        data = (raw.get(path) or {}).get("data")
        if not isinstance(data, dict):
            continue
        for field, keys in FIELDS.items():
            info[field] = info[field] or next((str(data[k]) for k in keys if data.get(k)), "")
    m = re.search(r"小红书(?:账)?号[:：]\s*([A-Za-z0-9_.-]+)", raw.get("text", ""))
    if m and not info["red_id"]:
        info["red_id"] = m.group(1)
    return info


async def export_port(p, port, dry):
    if not cdp_alive(port):
        return None
    ensure_page(port, "creator.xiaohongshu.com", "https://creator.xiaohongshu.com/new/home")
    browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    ctx = browser.contexts[0]
    page = next((pg for pg in ctx.pages if "creator.xiaohongshu.com" in pg.url), None)
    if page is None:
        return {"port": port, "status": "没有创作服务平台页面"}
    if "/login" in page.url:
        return {"port": port, "status": "未登录", "url": page.url}
    try:
        raw = await page.evaluate(INFO_JS)
    except Exception as e:
        raw = {"error": str(e)[:150]}
    info = user_info(raw)
    red_id, user_id, nickname = info["red_id"], info["user_id"], info["nickname"]
    if dry or not red_id:
        shown = {k: v for k, v in raw.items() if k != "text"}
        print(f"[{port}] 接口返回：{json.dumps(shown, ensure_ascii=False)[:600]}")
        print(f"[{port}] 页面文字：{raw.get('text', '')[:300]!r}")
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", red_id or user_id) or f"port{port}"
    r = {"port": port, "status": "已识别" if dry else "已导出", "account": key, "nickname": nickname,
         "red_id": red_id, "user_id": user_id, "url": page.url}
    if dry:
        return r
    out = f"cookies/xiaohongshu_{key}.json"
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
    return r


async def main(n, dry):
    rows = []
    async with async_playwright() as p:
        for i in range(1, n + 1):
            try:
                r = await export_port(p, BASE_PORT + i, dry)
            except Exception as e:
                r = {"port": BASE_PORT + i, "status": f"出错：{str(e)[:150]}"}
            if r:
                rows.append(r)
    new = [r for r in rows if r["status"] == "已导出"]
    if new:
        exists = os.path.exists(REGISTRY)
        with open(REGISTRY, "a") as f:
            if not exists:
                f.write("account\tnickname\tred_id\tuser_id\texported_at\tport\n")
            for r in new:
                f.write(f"{r['account']}\t{r['nickname']}\t{r['red_id']}\t{r['user_id']}\t"
                        f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{r['port']}\n")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    if not rows:
        print("没有找到打开的登录窗口")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(int(args[0]) if args else 3, "--dry" in sys.argv))
