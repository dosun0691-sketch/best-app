
import sys
from playwright.sync_api import sync_playwright
src = sys.argv[1]; jobs = [x.split("=") for x in sys.argv[2:]]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    for size, out in jobs:
        pg = b.new_page(viewport={"width":512,"height":512}, device_scale_factor=int(size)/512)
        pg.goto("file:///" + src); pg.wait_for_timeout(200); pg.screenshot(path=out); pg.close()
    b.close()
print("ok")
