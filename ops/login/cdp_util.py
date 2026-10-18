"""导出脚本共用的调试端口小工具。"""
import json
import time
import urllib.request


def cdp_alive(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
        return True
    except Exception:
        return False


def ensure_page(port, domain, url, wait=6):
    """没有 domain 的页面就新开一个 url。

    扫完码把窗口关掉时，Chrome 进程和登录态都还在，但没有页面可连，
    connect_over_cdp 会报 "Browser context management is not supported"。
    """
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as r:
        targets = json.load(r)
    if any(t.get("type") == "page" and domain in t.get("url", "") for t in targets):
        return
    print(f"[{port}] 没有 {domain} 页面（窗口可能被关了），重开 {url}")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{url}", method="PUT")
    urllib.request.urlopen(req, timeout=5).close()
    time.sleep(wait)  # 等页面加载完、该跳登录页的跳过去
