
import sys
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    pg = b.new_page(viewport={"width":390,"height":844}, device_scale_factor=2)
    errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("https://ourfamily-best-1117.web.app/"); pg.wait_for_selector("#gBtn", timeout=20000)
    print("live sign-in visible:", pg.is_visible("#gBtn"), "| tabs hidden:", pg.is_hidden("#tabs"), "| errors:", errs)
    pg.screenshot(path=r"C:/Users/apple/best-app/shots/0-signin-live.png")
    b.close()
