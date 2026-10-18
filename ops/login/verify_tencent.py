"""用会话文件在全新的无界面浏览器里打开视频号助手，读本号信息，确认会话真能用。

比 `sau tencent check` 严：后者只看 8 秒内有没有跳回登录页。
用法：python ops/login/verify_tencent.py <账号名>...
"""
import asyncio
import os
import sys
from pathlib import Path

from patchright.async_api import async_playwright

from export_tencent import AUTH_JS, finder_user

os.chdir(Path(__file__).resolve().parents[2])


async def main(accounts):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for a in accounts:
            ctx = await browser.new_context(storage_state=f"cookies/tencent_{a}.json")
            page = await ctx.new_page()
            await page.goto("https://channels.weixin.qq.com/platform/", wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
            try:
                fu = finder_user(await page.evaluate(AUTH_JS))
                print(a, "ok" if fu.get("uniqId") == a else "MISMATCH", fu.get("nickname"), page.url)
            except Exception as e:
                print(a, "error", str(e)[:120], page.url)
            await ctx.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
