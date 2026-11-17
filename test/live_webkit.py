
import sys
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.webkit.launch(); d = dict(p.devices["iPhone 14"])
    c0 = b.new_context(**d); p0 = c0.new_page(); p0.goto("https://ourfamily-best-1117.web.app/install.html"); f = d["viewport"]["width"] / p0.evaluate("innerWidth"); c0.close()
    d["viewport"] = {"width": round(390*f), "height": round(664*f)}; d["is_mobile"] = False
    for lang in ("ko", "zh"):
        c = b.new_context(**d); pg = c.new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script(f"localStorage.setItem('best.lang', '{lang}')")
        pg.goto("https://ourfamily-best-1117.web.app/"); pg.wait_for_selector("#noKey", timeout=20000)
        meta = pg.evaluate("[innerWidth, document.title, !!document.querySelector('link[rel=apple-touch-icon][href=\"icon-180.png\"]'), !document.querySelector('link[rel=manifest]'), document.querySelector('meta[name=apple-mobile-web-app-capable]').content, document.querySelector('meta[name=apple-mobile-web-app-status-bar-style]').content, getComputedStyle(document.documentElement).touchAction]")
        print("live webkit", lang, "no-key screen ok", meta, "errors:", errs, flush=True)
        pg.screenshot(path=f"C:/Users/apple/best-app/shots/webkit/live-{lang}-nokey.png")
        pg.goto("https://ourfamily-best-1117.web.app/install.html"); pg.wait_for_selector("ol"); pg.screenshot(path=f"C:/Users/apple/best-app/shots/webkit/live-{lang}-install.png", full_page=True)
        c.close()
    b.close()
