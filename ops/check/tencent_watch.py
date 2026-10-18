"""视频号会话存活测试：定时用会话文件打开视频号助手、读本号信息，记录会话有没有掉线。

用法：python ops/check/tencent_watch.py --keep A B --rare C D [--every 30] [--rare-every 240]
  --keep 组：每 --every 分钟查一次，查完把最新会话写回文件，相当于一直有人在用
  --rare 组：每 --rare-every 分钟查一次，不写回
日志：logs/tencent-watch.log，每行用制表符分隔：时间、账号、组、结果（ok/expired/mismatch/error）、页面网址
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from patchright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "login"))
from export_tencent import AUTH_JS, finder_user  # noqa: E402

os.chdir(Path(__file__).resolve().parents[2])
LOG = Path("logs/tencent-watch.log")


async def check(browser, account, persist):
    path = f"cookies/tencent_{account}.json"
    ctx = await browser.new_context(storage_state=path)
    try:
        page = await ctx.new_page()
        await page.goto("https://channels.weixin.qq.com/platform/", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        if "login.html" in page.url:
            return "expired", page.url
        if finder_user(await page.evaluate(AUTH_JS)).get("uniqId") != account:
            return "mismatch", page.url
        if persist:
            await ctx.storage_state(path=path)
            os.chmod(path, 0o600)
        return "ok", page.url
    except Exception as e:
        return f"error:{str(e)[:80]}", ""
    finally:
        await ctx.close()


async def main(args):
    LOG.parent.mkdir(exist_ok=True)
    start = time.time()
    tick = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        while True:
            jobs = [("keep", a, True) for a in args.keep]
            if (tick * args.every) % args.rare_every == 0:
                jobs += [("rare", a, False) for a in args.rare]
            for group, account, persist in jobs:
                result, url = await check(browser, account, persist)
                line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{account}\t{group}\t{result}\t{url}"
                print(line, flush=True)
                with LOG.open("a") as f:
                    f.write(line + "\n")
            tick += 1
            await asyncio.sleep(max(0, start + tick * args.every * 60 - time.time()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", nargs="*", default=[])
    ap.add_argument("--rare", nargs="*", default=[])
    ap.add_argument("--every", type=int, default=30, help="keep 组的检查间隔（分钟）")
    ap.add_argument("--rare-every", type=int, default=240, help="rare 组的检查间隔（分钟），须是 --every 的整数倍")
    asyncio.run(main(ap.parse_args()))
