
import sys, asyncio
from playwright.sync_api import sync_playwright
src, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    for size in (512, 192, 180, 1024):
        pg = b.new_page(viewport={"width":512,"height":512}, device_scale_factor=size/512)
        pg.goto("file:///" + src.replace("\\","/"))
        pg.wait_for_timeout(300)
        pg.screenshot(path=f"{out}/icon-{size}.png")
        pg.close()
    b.close()
print("ok")
