
# Live smoke test (production). Reads the church key from the git-ignored invite-code.txt - the key is never in this file.
# It creates one real test device (anonymous user + staff doc named 동역자/同工): remove it afterwards (staff/{uid}, staffKeys/{uid}, auth user).
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
HOST = "https://ourfamily-best-1117.web.app"
KEY = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "invite-code.txt"), encoding="utf-8").read().split()[0]
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shots")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    for lang in ("ko", "zh"):
        c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2); pg = c.new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script(f"localStorage.setItem('best.lang', '{lang}')")
        pg.goto(HOST + "/"); pg.wait_for_selector("#noKey", timeout=20000)
        print("live", lang, "no-key screen:", pg.is_visible("#noKey"), "| tabs hidden:", pg.is_hidden("#tabs"), "| logo loaded:", pg.evaluate("document.querySelector('img.biglogo').naturalWidth"), "| errors:", errs, flush=True)
        pg.screenshot(path=os.path.join(SHOTS, f"live-{lang}-nokey.png")); c.close()
    c = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2); pg = c.new_page(); errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(HOST + "/?k=WRONGKEY2026ABCD"); pg.wait_for_selector("#codeErr", timeout=30000)
    print("live wrong key -> denied:", pg.is_visible("#codeErr"), "| key forgotten:", pg.evaluate("localStorage.getItem('best.key')") is None, "| tabs hidden:", pg.is_hidden("#tabs"), flush=True)
    wrong_uid = pg.evaluate("(window.__me && window.__me()) || null")
    pg.goto(HOST + "/install.html?k=" + KEY); pg.wait_for_selector("#openApp")
    print("live install page: key stripped from URL:", pg.evaluate("location.search") == "", flush=True)
    pg.click("#openApp"); pg.wait_for_selector("#tabs:not([hidden])", timeout=30000); pg.wait_for_timeout(2500)
    print("live right key -> auto-joined, tabs visible:", pg.is_visible("#tabs"), "| ask name:", pg.is_visible("#askNm"), "| errors:", errs, flush=True)
    pg.screenshot(path=os.path.join(SHOTS, "live-joined-home.png"))
    c.close(); b.close()
