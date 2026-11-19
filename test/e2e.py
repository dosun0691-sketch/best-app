
# E2E against Firebase emulators (auth+firestore+hosting). Run via: firebase emulators:exec --only auth,firestore,hosting --project demo-best "python -I test/e2e.py"
import json, sys, urllib.request, datetime, os, struct
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
FS = "http://127.0.0.1:8080/v1/projects/demo-best/databases/(default)/documents"
H = {"Authorization": "Bearer owner", "Content-Type": "application/json"}
ENGINE = sys.argv[1] if len(sys.argv) > 1 else "edge"   # edge (Chromium = Android TWA engine) | webkit (iPhone Safari engine)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shots", ENGINE)
import re
os.makedirs(OUT, exist_ok=True)
results = []
ZPAGE = []
def check(name, ok, info=""):
    if ZPAGE:
        try:
            z = ZPAGE[0].evaluate("[Math.round(visualViewport.width), Math.round(visualViewport.scale*100)/100, document.documentElement.scrollWidth, document.activeElement && document.activeElement.id]")
            print("   zoom-trace", z, flush=True)
        except Exception: pass
    results.append((name, bool(ok))); print(("PASS " if ok else "FAIL ") + name + (" :: " + str(info) if info else ""), flush=True)
def req(method, path, body=None):
    r = urllib.request.Request(FS + path, data=json.dumps(body).encode() if body is not None else None, headers=H, method=method)
    with urllib.request.urlopen(r) as f: return json.loads(f.read() or b"{}")
def val(v):
    if isinstance(v, bool): return {"booleanValue": v}
    if isinstance(v, datetime.datetime): return {"timestampValue": v.strftime("%Y-%m-%dT%H:%M:%SZ")}
    if isinstance(v, int): return {"integerValue": str(v)}
    if isinstance(v, list): return {"arrayValue": {"values": [val(x) for x in v]}}
    if isinstance(v, dict): return {"mapValue": {"fields": {k: val(x) for k, x in v.items()}}}
    return {"stringValue": v}
def put(path, data): req("PATCH", path, {"fields": {k: val(v) for k, v in data.items()}})
def unval(v):
    k = list(v.keys())[0]; x = v[k]
    if k == "arrayValue": return [unval(i) for i in x.get("values", [])]
    if k == "mapValue": return {a: unval(b) for a, b in x.get("fields", {}).items()}
    if k == "integerValue": return int(x)
    return x
def get(path): d = req("GET", path); return {k: unval(v) for k, v in d.get("fields", {}).items()}
def lst(path): d = req("GET", path); return [(x["name"].split("/")[-1], {k: unval(v) for k, v in x.get("fields", {}).items()}) for x in d.get("documents", [])]

today = datetime.date.today(); T = today.isoformat()
def sun(n):  # n-th most recent Sunday (0 = this/last Sunday)
    d = today - datetime.timedelta(days=(today.weekday() + 1) % 7); return (d - datetime.timedelta(weeks=n)).isoformat()
# ---------- seed (sample data only) ----------
KEY = "TESTC0DE2026KEYX"   # church key carried by the QR link
put("/config/invite", {"code": KEY})
put("/staff/staff-lee", {"name": "李姊妹", "active": True, "role": "staff"})
put("/staff/staff-park", {"name": "박집사", "active": True, "role": "staff"})
base = {"createdAt": datetime.datetime.utcnow(), "updatedAt": datetime.datetime.utcnow(), "cls": [False]*5, "lastContact": "", "nextAction": "", "nextDue": "", "createdBy": "staff-lee", "updatedBy": "staff-lee"}
seed = {
 "b-chen": {"name": "陳小明", "firstVisit": sun(0), "stage": "first", "caretaker": "staff-lee", "phone": "0912-345-678", "line": "chen_sm", "nick": "Ming"},
 "b-lin": {"name": "林美華", "firstVisit": sun(1), "stage": "first", "caretaker": "staff-park"},
 "b-zhang": {"name": "張志豪", "firstVisit": sun(6), "stage": "revisit", "caretaker": "staff-lee", "lastContact": sun(4)},
 "b-wang": {"name": "王淑芬", "firstVisit": sun(9), "stage": "class", "cls": [True, True, True, False, False], "lastContact": sun(1), "caretaker": "staff-park"},
 "b-huang": {"name": "黃建國", "firstVisit": sun(9), "stage": "group", "lastContact": sun(2)},
 "b-wu": {"name": "吳佳蓉", "firstVisit": sun(9), "stage": "welcome", "lastContact": sun(8)},
 "b-kim": {"name": "김하늘", "firstVisit": sun(2), "stage": "welcome", "lastContact": sun(2), "nextAction": "주중 LINE으로 안부", "nextDue": (today - datetime.timedelta(days=2)).isoformat(), "caretaker": "staff-park", "nick": "하늘이"},
 "b-liu": {"name": "劉家豪", "firstVisit": sun(12), "stage": "settled", "lastContact": sun(3)},
 "b-tsai": {"name": "蔡雅婷", "firstVisit": sun(10), "stage": "paused", "lastContact": sun(7)},
}
for k, v in seed.items():
    d = dict(base); d.update(v); d["stageHistory"] = [{"s": "first", "d": d["firstVisit"], "by": "staff-lee"}]; put("/bests/" + k, d)
att = {n: [] for n in range(10)}
for n in range(10):
    for k in ["b-wang", "b-huang", "b-liu"]: att[n].append(k)
for n in (5, 6): att[n].append("b-zhang")
att[9].append("b-wu"); att[1].append("b-lin"); att[0].append("b-chen"); att[2].append("b-kim"); att[1].append("b-kim")
for n, ids in att.items(): put("/attendance/" + sun(n), {"ids": ids, "by": "staff-lee"})
put("/bests/b-wang/notes/n-lee", {"text": "喜歡唱詩歌，可以邀請加入詩班", "by": "staff-lee", "byName": "李姊妹", "at": datetime.datetime.utcnow()})
put("/bests/b-wang/logs/l1", {"date": sun(1), "method": "visit", "content": "家庭探訪，一起吃晚餐", "prayer": "工作穩定", "by": "staff-park"})

# ---------- crop test picture (O62): 800x400, left half red, right half blue (24-bit BMP, no extra libraries) ----------
def bmp(w, h, px):
    row = (w * 3 + 3) & ~3; data = bytearray()
    for y in range(h - 1, -1, -1):
        r = bytearray()
        for x in range(w): R_, G_, B_ = px(x, y); r += bytes((B_, G_, R_))
        data += r + b"\0" * (row - w * 3)
    return b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54) + struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(data), 2835, 2835, 0, 0) + bytes(data)
CROPIMG = {"name": "crop-test.bmp", "mimeType": "image/bmp", "buffer": bmp(800, 400, lambda x, y: (220, 30, 30) if x < 400 else (30, 60, 220))}
GEO = "() => { const s = document.querySelector('#cropSt').getBoundingClientRect(), i = document.querySelector('#cropImg').getBoundingClientRect(); return [s.left, s.top, s.width, s.height, i.left - s.left, i.top - s.top, i.width]; }"
PIX = """async (pts) => { const src = document.querySelector('#phPrev img').src; const im = new Image(); im.src = src; await im.decode();
  const c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight; const x = c.getContext('2d'); x.drawImage(im, 0, 0);
  return [im.naturalWidth, im.naturalHeight, src.length, pts.map(([a, b]) => [...x.getImageData(a, b, 1, 1).data.slice(0, 3)])]; }"""
TOUCH = """(steps) => { const st = document.querySelector('#cropSt');
  for (const [type, id, x, y] of steps) st.dispatchEvent(new PointerEvent(type, { pointerId: id, pointerType: 'touch', isPrimary: id === 11, clientX: x, clientY: y, bubbles: true, cancelable: true, buttons: type === 'pointerup' ? 0 : 1 })); }"""
RED = lambda p: p[0] > 150 and p[1] < 100 and p[2] < 100
BLUE = lambda p: p[2] > 150 and p[0] < 100
near = lambda a, b, tol=2: abs(a - b) <= tol

errors = []
def W(page, sel, timeout=20000):   # wait_for_selector + state dump on timeout
    try: return page.wait_for_selector(sel, timeout=timeout)
    except Exception:
        print("DEBUG-WAIT", sel, page.evaluate("[window.__me && window.__me(), Object.keys(localStorage), location.href, document.querySelector('#view') && document.querySelector('#view').innerText.slice(0, 300)]"), errors[-6:], flush=True); raise
def go(page, h):   # in-app navigation by hash (WebKit/iPhone keeps ?k= in the URL, so a plain goto("/#x") would be a full reload)
    if "/install.html" in page.url or not page.url.startswith("http://127.0.0.1:5000/"):
        k = page.evaluate("localStorage.getItem('best.key')") if page.url.startswith("http://127.0.0.1:5000/") else None
        return page.goto("http://127.0.0.1:5000/" + ("?k=" + k if (ENGINE == "webkit" and k) else "") + h)
    page.evaluate("(h) => { location.hash = h; }", h); page.wait_for_timeout(150)
with sync_playwright() as p:
    if ENGINE == "webkit":
        br = p.webkit.launch(); DEV = dict(p.devices["iPhone 14"])
        # Windows WebKit applies the OS display scale (e.g. 120%) on top of the device scale -> CSS width 325 instead of 390.
        # Measure that factor and compensate so the page sees exactly the iPhone 14 CSS viewport (390 wide).
        _c = br.new_context(**DEV); _p = _c.new_page(); _p.goto("http://127.0.0.1:5000/install.html"); f = DEV["viewport"]["width"] / _p.evaluate("innerWidth"); _c.close()
        DEV["viewport"] = {"width": round(DEV["viewport"]["width"] * f), "height": round(DEV["viewport"]["height"] * f)}
        DEV["is_mobile"] = False   # mobile meta-viewport emulation is broken by the DPI scale on Windows WebKit; window = 390 CSS px already
        if "screen" in DEV: DEV["screen"] = {"width": round(DEV["screen"]["width"] * f), "height": round(DEV["screen"]["height"] * f)}
    else:
        br = p.chromium.launch(executable_path=r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
        DEV = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True}
    print("engine:", ENGINE, br.version, DEV.get("viewport"), flush=True)
    FX = DEV["viewport"]["width"] / 390   # Windows WebKit DPI compensation factor (1 for Edge)
    _c = br.new_context(**DEV); _p = _c.new_page(); _p.goto("http://127.0.0.1:5000/install.html")
    print("css viewport:", _p.evaluate("[innerWidth, innerHeight, Math.round(devicePixelRatio*100)/100, navigator.userAgent]"), flush=True); _c.close()
    ctx = br.new_context(**DEV, locale="ko-KR", accept_downloads=True)
    pg = ctx.new_page()
    if ENGINE == "webkit": ZPAGE.append(pg)
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    IOSLIKE = ENGINE == "webkit"   # iPhone 14 UA -> the app treats it as iPhone Safari (not yet on the home screen)
    pg.goto("http://127.0.0.1:5000/")
    pg.wait_for_selector("#noKey")
    check("no key (not opened from the QR): only the 'scan the church QR' screen, no tabs", pg.is_hidden("#tabs") and "請用教會的 QR 碼開啟" in pg.inner_text("#view"))  # default language = zh (owner 2026-11-17)
    check("first open defaults to Chinese even on a Korean phone (owner 2026-11-17); Korean only when chosen", pg.evaluate("document.documentElement.lang") == "zh-Hant-TW")
    pg.click("#langBtn"); pg.wait_for_selector("text=교회 QR코드로 열어 주세요")   # rest of the flow runs in Korean (chosen)
    check("no-key visitor is not signed in at all (Firestore closed to them)", pg.evaluate("window.__me()") is None)
    lg = pg.evaluate("[...document.querySelectorAll('img.clogo, img.biglogo')].map((i) => [i.className, i.naturalWidth, Math.round(i.getBoundingClientRect().width)])")
    check("church logo: small in header + large centered on the no-key screen (loaded)", ["clogo", 256, 36] in lg and ["biglogo", 256, 150] in lg, lg)
    pg.screenshot(path=f"{OUT}/flow-0-nokey-ko.png")
    pg.goto("http://127.0.0.1:5000/?k=WRONGKEY2026ABCD"); pg.wait_for_selector("#codeErr", timeout=20000)
    w = pg.evaluate("window.__me()")
    check("wrong key: join denied, 'code not valid' shown, key forgotten, no staff doc", pg.is_hidden("#tabs") and pg.evaluate("localStorage.getItem('best.key')") is None and w and not [x for x in lst("/staff") if x[0] == w["uid"]], w)
    pg.screenshot(path=f"{OUT}/flow-1-wrongkey-ko.png")
    pg.goto(f"http://127.0.0.1:5000/install.html?k={KEY.lower()}"); pg.wait_for_selector("#openApp")
    st = pg.evaluate("[localStorage.getItem('best.key'), location.search, document.getElementById('openApp').getAttribute('href')]")
    check("install page header shows the church logo", pg.evaluate("[document.querySelector('.top img.clogo').naturalWidth, Math.round(document.querySelector('.top img.clogo').getBoundingClientRect().width)]") == [256, 40])
    check("QR link install.html?k=: key stored, stripped from the address bar, 'open BEST' button carries it", st == [KEY, "", "./?k=" + KEY], st)
    pg.click("#openApp"); pg.wait_for_selector("#tabs:not([hidden])", timeout=20000)
    who = pg.evaluate("window.__me()"); uid = who["uid"]
    me = get("/staff/" + uid)
    check("key holder auto-joins: anonymous device, active plain staff, default name, nothing typed", who["anon"] and me["role"] == "staff" and me["active"] is True and me["name"] == "동역자", (who, me))
    url = pg.evaluate("[location.search, !!document.querySelector('link[rel=manifest]')]")
    if IOSLIKE: check("iPhone Safari: key kept in the URL and no manifest (Add to Home Screen saves this URL)", url == ["?k=" + KEY, False], url)
    else: check("Android/Chrome: key stripped from the URL, manifest linked", url == ["", True], url)
    check("iPhone Safari shows the 'add to home screen' tip (and only there)", pg.is_visible("#iosTip") == IOSLIKE)
    check("first open asks only for an optional name", pg.is_visible("#askNm") and pg.locator("#view input").count() == 1)
    pg.wait_for_timeout(800)
    pg.screenshot(path=f"{OUT}/flow-2a-joined-home-ko.png")
    pg.fill("#askNm", "김목자"); pg.click("#askSave"); pg.wait_for_timeout(1000)
    check("optional name saved (author on contact logs); prompt gone", get("/staff/" + uid)["name"] == "김목자" and pg.locator("#askNm").count() == 0)
    pg.wait_for_selector("text=오늘 돌봐야 할 BEST")
    pg.wait_for_timeout(800)
    body = pg.inner_text("#view")
    sec = lambda title: pg.locator(".card.alert", has_text=title).inner_text() if pg.locator(".card.alert", has_text=title).count() else ""
    nc, ab, du = sec("첫 연락 전"), sec("연속 결석"), sec("해야 할 일")
    check("dashboard (a) no-contact: 陳小明 + 林美華(overdue)", "陳小明" in nc and "林美華" in nc and "일 지남" in nc, nc.replace("\n", " | "))
    check("dashboard (b) absent 2+ Sundays: 張志豪, 吳佳蓉; not 王淑芬", "張志豪" in ab and "吳佳蓉" in ab and "王淑芬" not in ab, ab.replace("\n", " | "))
    check("dashboard (c) due/overdue: 김하늘", "김하늘" in du and "2일 지남" in du, du.replace("\n", " | "))
    stats = pg.inner_text(".stats")
    check("dashboard (d) counts + 8-week retention 3/5 (王 class+attending, 黃 group, 劉 settled kept; 吳 absent, 蔡 paused not)", "60%" in stats and "(3/5)" in stats, stats.replace("\n", " | "))
    pg.screenshot(path=f"{OUT}/flow-2-home-ko.png")
    # register
    pg.click("#fab"); pg.wait_for_selector("#f_name")
    pg.fill("#f_name", "周恩惠"); pg.fill("#f_nick", "Grace"); pg.select_option("#f_gender", "f"); pg.select_option("#f_age", "30")
    check("phone / LINE ID fields are gone from the form", pg.locator("#f_phone, #f_line").count() == 0)
    pg.fill("#f_job", "設計師"); pg.fill("#f_school", "台灣師大(美術系)"); pg.fill("#f_grade", "研一"); pg.fill("#f_area", "台北市 信義區")
    pg.fill("#f_invitedBy", "王淑芬"); pg.select_option("#f_faith", "moved"); pg.fill("#f_family", "先生、女兒(5歲)")
    pg.fill("#f_prayer", "女兒身體健康"); pg.fill("#f_memo", "喜歡詩歌")
    pg.select_option("#f_caretaker", "staff-lee")
    pg.set_input_files("#f_photo", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "icon-512.png"))
    pg.wait_for_selector("#cropDlg"); pg.click("#cropSave"); pg.wait_for_selector("#cropDlg", state="detached")   # crop dialog (O62): keep the default centred square
    pg.wait_for_timeout(500)
    fm = pg.evaluate("""() => { const m = document.querySelector('#f_memo'), p = document.querySelector('#f_prayer');
      return [Math.round(document.querySelector('#phPrev .ava').getBoundingClientRect().width), m.closest('label').textContent.trim(), !!(m.compareDocumentPosition(p) & 4),
              document.querySelector('#f_nick').maxLength, document.querySelector('#f_nick').closest('label').textContent.trim()]; }""")
    check("register: bigger photo picker (>=128px), nickname field (max 20), memo label '기억해 둘 일' placed before prayer", fm[0] >= 128 and fm[1] == "기억해 둘 일" and fm[2] and fm[3] == 20 and fm[4] == "별명", fm)
    pg.screenshot(path=f"{OUT}/flow-3-register-ko.png"); pg.screenshot(path=f"{OUT}/flow-3-register-ko-full.png", full_page=True)
    pg.click("#fSave"); pg.wait_for_selector(".pipe"); pg.wait_for_timeout(500)
    bid = pg.evaluate("location.hash").split("/")[1]
    b = get("/bests/" + bid)
    check("BEST registered with all fields (incl. nickname)", b["name"] == "周恩惠" and b.get("nick") == "Grace" and b["job"] == "設計師" and b["school"] == "台灣師大(美術系)" and b["grade"] == "研一" and "phone" not in b and "line" not in b and b["faith"] == "moved" and b["photo"].startswith("data:image/jpeg") and len(b["photo"]) < 300000, {k: (v if k != "photo" else len(v)) for k, v in b.items() if k not in ("createdAt", "updatedAt")})
    check("caretaker assigned at registration", b["caretaker"] == "staff-lee")
    dt = pg.evaluate("""() => [document.querySelector('.hero .nm').textContent.trim(), Math.round(document.querySelector('.hero .ava').getBoundingClientRect().width),
      [...document.querySelectorAll('dl.kv dt')].map((e) => e.textContent)]""")
    check("detail: name + (nickname), photo ~double (>=160px), memo '기억해 둘 일' before prayer", dt[0] == "周恩惠 (Grace)" and dt[1] >= 160 and dt[2].index("기억해 둘 일") < dt[2].index("기도 제목"), dt)
    kvt = pg.inner_text("dl.kv")
    check("detail shows occupation / school(dept) / grade; no phone / LINE", all(x in kvt for x in ("직업", "設計師", "학교(과)", "台灣師大(美術系)", "학년", "研一")) and "전화" not in kvt and "LINE" not in kvt, kvt.replace("\n", " | "))
    # supplements (보충) under the memo
    pg.fill("#suppTxt", "첫 만남 때 커피를 좋아한다고 함"); pg.click("#suppAdd"); pg.wait_for_function("() => document.querySelectorAll('#suppList .sn').length === 1", timeout=15000)
    pg.wait_for_timeout(300)
    pg.fill("#suppTxt", "딸 유치원 근처에 삼"); pg.click("#suppAdd"); pg.wait_for_function("() => document.querySelectorAll('#suppList .sn').length === 2", timeout=15000)
    pg.wait_for_timeout(500)
    ns = lst("/bests/" + bid + "/notes"); sn = pg.locator("#suppList .sn").all_inner_texts()
    pos = pg.evaluate("""() => { const dts = [...document.querySelectorAll('dl.kv dt')], box = document.querySelector('#suppBox');
      const memo = dts.find((d) => d.textContent === '기억해 둘 일'), pr = dts.find((d) => d.textContent === '기도 제목');
      return [!!(memo.compareDocumentPosition(box) & 4), !!(box.compareDocumentPosition(pr) & 4)]; }""")
    check("supplement: box right under memo (before prayer); entries newest last with auto date-time + author name",
          pos == [True, True] and len(ns) == 2 and all(n[1]["by"] == uid and n[1]["byName"] == "김목자" for n in ns)
          and "첫 만남" in sn[0] and "딸 유치원" in sn[1] and ("보충 일시 " + T) in sn[0] and "보충자 김목자" in sn[0], (pos, sn))
    pg.screenshot(path=f"{OUT}/flow-4b-supplement-ko.png", full_page=(ENGINE != "webkit"))
    pg.locator("#suppList .sn", has_text="첫 만남").locator("[data-ndel]").click(); pg.wait_for_function("() => document.querySelectorAll('#suppList .sn').length === 1", timeout=15000)
    for _ in range(20):
        left_ = [n[1]["text"] for n in lst("/bests/" + bid + "/notes")]
        if len(left_) == 1: break
        pg.wait_for_timeout(250)
    check("supplement: author deletes own entry", left_ == ["딸 유치원 근처에 삼"], left_)
    pg.select_option("#careSel", "staff-park"); pg.wait_for_timeout(800)
    check("caretaker re-assigned from detail", get("/bests/" + bid)["caretaker"] == "staff-park")
    pg.click("[data-st=welcome]"); pg.wait_for_timeout(800)
    pg.click("[data-st=revisit]"); pg.wait_for_timeout(800)
    b = get("/bests/" + bid)
    check("stage moved + history kept", b["stage"] == "revisit" and [x["s"] for x in b["stageHistory"]] == ["first", "welcome", "revisit"], b["stageHistory"])
    check("BEST class (5 weeks) card removed", pg.locator("[data-wk]").count() == 0)
    pg.click("#addLogBtn"); pg.select_option("#l_method", "line")
    pg.fill("#l_content", "LINE로 환영 인사, 다음 주일 다시 오기로"); pg.fill("#l_prayer", "딸의 건강"); pg.fill("#l_next", "주일 예배 후 식사 초대")
    pg.fill("#l_due", T); pg.click("#l_save"); pg.wait_for_timeout(1200)
    logs = lst("/bests/" + bid + "/logs"); b = get("/bests/" + bid)
    check("contact log saved + lastContact/nextAction updated", len(logs) == 1 and logs[0][1]["method"] == "line" and b["lastContact"] == T and b["nextDue"] == T, (logs, b["lastContact"], b["nextAction"]))
    pg.wait_for_selector(".log")
    pg.screenshot(path=f"{OUT}/flow-4-detail-ko.png")
    # ---------- photo crop dialog (O62): drag to move, slider / pinch / wheel to zoom, saved avatar = chosen area ----------
    go(pg, "#edit/" + bid); pg.wait_for_selector("#f_name"); pg.wait_for_timeout(400)
    check("edit form: existing photo shows the 'adjust photo' button", pg.is_visible("#phAdj") and pg.inner_text("#phAdj") == "사진 조정")
    pg.screenshot(path=f"{OUT}/crop-0-before-ko.png")
    pg.set_input_files("#f_photo", files=[CROPIMG]); pg.wait_for_selector("#cropDlg"); pg.wait_for_timeout(300)
    g = pg.evaluate(GEO); F = g[2]
    check("crop dialog: square frame, picture covers it, centred", near(g[2], g[3]) and F >= 300 and near(g[6], 2 * F) and near(g[4], -F / 2) and near(g[5], 0), g)
    check("crop dialog fits the phone width (390px), no overflow", pg.evaluate("[...document.querySelectorAll('#cropDlg *:not(#cropImg)')].every((e) => e.getBoundingClientRect().right <= innerWidth + 1) && document.documentElement.scrollWidth <= innerWidth + 1"))
    pg.screenshot(path=f"{OUT}/crop-1-open-ko.png")
    cx, cy = g[0] + F / 2, g[1] + F / 2
    pg.fill("#cropZoom", "2"); pg.dispatch_event("#cropZoom", "input"); g2 = pg.evaluate(GEO)
    check("crop: zoom slider x2 doubles the picture size", near(g2[6], 4 * F), (g2[6], 4 * F))
    pg.evaluate(TOUCH, [["pointerdown", 11, cx - 40, cy], ["pointerdown", 12, cx + 40, cy], ["pointermove", 12, cx + 80, cy], ["pointerup", 12, cx + 80, cy], ["pointerup", 11, cx - 40, cy]])
    g3 = pg.evaluate(GEO)
    check("crop: two-finger pinch zooms (80px -> 120px apart = x1.5)", near(g3[6], 6 * F, 3), (g3[6], 6 * F))
    pg.screenshot(path=f"{OUT}/crop-2-zoomed-ko.png")
    pg.fill("#cropZoom", "1"); pg.dispatch_event("#cropZoom", "input"); gb = pg.evaluate(GEO)
    pg.evaluate(TOUCH, [["pointerdown", 11, cx, cy], ["pointermove", 11, cx + 30, cy + 25], ["pointerup", 11, cx + 30, cy + 25]])
    g4 = pg.evaluate(GEO)
    check("crop: one-finger drag moves the picture (sideways only as far as the edge; no vertical room at x1)", near(g4[4], gb[4] + 30) and near(g4[5], 0) and near(gb[6], 2 * F), (gb, g4))
    pg.mouse.move(cx, cy); pg.mouse.down(); pg.mouse.move(cx + F * 0.3, cy, steps=5); pg.mouse.move(cx + F, cy, steps=5); pg.mouse.up()
    g5 = pg.evaluate(GEO)
    check("crop: mouse drag moves it; stops at the picture edge (no empty border)", near(g5[4], 0) and near(g5[6], 2 * F), g5)
    pg.screenshot(path=f"{OUT}/crop-3-moved-left-part-ko.png")
    pg.click("#cropSave"); pg.wait_for_selector("#cropDlg", state="detached")
    px = pg.evaluate(PIX, [[20, 200], [200, 200], [380, 200], [200, 20], [200, 380]])
    check("crop saved: 400x400 JPEG <= 280KB showing ONLY the chosen (left, red) part", px[0] == 400 and px[1] == 400 and px[2] <= 280000 and all(RED(p) for p in px[3]), px)
    pg.screenshot(path=f"{OUT}/crop-4-after-ko.png")
    saved = pg.evaluate("document.querySelector('#phPrev img').src")
    pg.click("#phAdj"); pg.wait_for_selector("#cropDlg"); g6 = pg.evaluate(GEO)
    check("adjust: re-opens the stored photo (square, covers the frame)", near(g6[6], g6[2]) and near(g6[4], 0))
    pg.click("#cropCancel"); pg.wait_for_selector("#cropDlg", state="detached")
    check("adjust -> cancel: photo unchanged", pg.evaluate("document.querySelector('#phPrev img').src") == saved)
    pg.set_input_files("#f_photo", files=[CROPIMG]); pg.wait_for_selector("#cropDlg"); pg.keyboard.press("Escape"); pg.wait_for_selector("#cropDlg", state="detached")
    check("new pick -> Esc/cancel keeps the previous photo", pg.evaluate("document.querySelector('#phPrev img').src") == saved)
    pg.click("#fSave"); pg.wait_for_selector(".pipe"); pg.wait_for_timeout(800)
    check("form Save stores the cropped photo", get("/bests/" + bid)["photo"] == saved)
    pg.screenshot(path=f"{OUT}/crop-5-detail-after-ko.png")
    # PC: mouse wheel zoom + mouse drag in a desktop window
    cp_ = br.new_context(viewport={"width": round(1280 * FX), "height": round(800 * FX)}); pp = cp_.new_page()
    pp.on("pageerror", lambda e: errors.append("pc:" + str(e)))
    pp.add_init_script("localStorage.setItem('best.lang', 'zh')")
    pp.goto(f"http://127.0.0.1:5000/?k={KEY}"); W(pp, "#tabs:not([hidden])", timeout=20000)
    pp.goto("http://127.0.0.1:5000/#edit/" + bid); W(pp, "#f_name"); pp.wait_for_timeout(400)
    pp.set_input_files("#f_photo", files=[CROPIMG]); pp.wait_for_selector("#cropDlg"); pp.wait_for_timeout(300)
    q = pp.evaluate(GEO); QF = q[2]; qx, qy = q[0] + QF / 2, q[1] + QF / 2
    pp.mouse.move(qx, qy); pp.mouse.wheel(0, -300); pp.wait_for_timeout(300); q2 = pp.evaluate(GEO)
    check("PC: mouse wheel zooms in (x e = 2.72)", near(q2[6], 2 * QF * 2.718, 4), (q2[6], 2 * QF * 2.718))
    pp.mouse.move(qx, qy); pp.mouse.down(); pp.mouse.move(qx - QF * 3, qy, steps=8); pp.mouse.up(); q3 = pp.evaluate(GEO)
    check("PC: mouse drag to the right part, stops at the edge", near(q3[4] + q3[6], QF), q3)
    pp.screenshot(path=f"{OUT}/crop-6-pc-zh.png")
    pp.click("#cropSave"); pp.wait_for_selector("#cropDlg", state="detached")
    qp = pp.evaluate(PIX, [[20, 200], [200, 200], [380, 200]])
    check("PC: saved avatar shows the chosen (right, blue) part", qp[0] == 400 and all(BLUE(p) for p in qp[3]), qp)
    pp.screenshot(path=f"{OUT}/crop-7-pc-after-zh.png")
    cp_.close()
    # attendance
    pg.click("a[data-tab=att]"); pg.wait_for_selector("#attDay")
    pg.fill("#attDay", sun(0)); pg.dispatch_event("#attDay", "change"); pg.wait_for_timeout(500)
    pg.click("[data-att='" + bid + "']"); pg.wait_for_timeout(1000)
    a = get("/attendance/" + sun(0))
    check("Sunday attendance checked", bid in a["ids"] and "b-chen" in a["ids"], a["ids"])
    pg.click("[data-att='b-chen']"); pg.wait_for_timeout(1000)
    a = get("/attendance/" + sun(0))
    check("attendance un-check works", "b-chen" not in a["ids"] and bid in a["ids"], a["ids"])
    pg.click("[data-att='b-chen']"); pg.wait_for_timeout(800)
    pg.screenshot(path=f"{OUT}/flow-5-attendance-ko.png")
    # home shows the new due item; mark done
    pg.click("a[data-tab=home]"); pg.wait_for_timeout(800)
    du = sec("해야 할 일")
    check("dashboard shows new BEST next action due today", "周恩惠" in du and "오늘" in du, du.replace("\n", " | "))
    # list + filters
    pg.click("a[data-tab=list]"); pg.wait_for_selector("#q")
    n_all = pg.locator("#listBox .item").count()
    pg.click("#stSeg button[data-s=first]"); n_first = pg.locator("#listBox .item").count()
    pg.click("#stSeg button[data-s='']"); pg.select_option("#careSel", "staff-park"); n_park = pg.locator("#listBox .item").count()
    pg.select_option("#careSel", ""); pg.fill("#q", "陳小"); pg.wait_for_timeout(200); n_q = pg.locator("#listBox .item").count()
    pg.fill("#q", "0912"); pg.wait_for_timeout(200); n_ph = pg.locator("#listBox .item").count()
    check("list: all 10 / stage first 2 / caretaker 박집사 4 / name search 1 / old phone not searchable 0", (n_all, n_first, n_park, n_q, n_ph) == (10, 2, 4, 1, 0), (n_all, n_first, n_park, n_q, n_ph))
    found = {}
    for q in ("rac", "GRA", "恩惠", "늘이", "MING", "ming", "하늘"):
        pg.fill("#q", q); pg.wait_for_timeout(200); found[q] = pg.locator("#listBox .item .n").all_inner_texts()
    check("search by part of NAME or NICKNAME, case-insensitive (zh/ko/en)", found["rac"] == ["周恩惠 (Grace)"] and found["GRA"] == ["周恩惠 (Grace)"] and found["恩惠"] == ["周恩惠 (Grace)"]
          and found["늘이"] == ["김하늘 (하늘이)"] and found["MING"] == found["ming"] == ["陳小明 (Ming)"] and found["하늘"] == ["김하늘 (하늘이)"], found)
    pg.fill("#q", "rac"); pg.wait_for_timeout(200); pg.screenshot(path=f"{OUT}/flow-6b-search-nick-ko.png")
    pg.fill("#q", ""); pg.wait_for_timeout(200)
    pg.screenshot(path=f"{OUT}/flow-6-list-ko.png")
    # tel: link + done button
    go(pg, "#best/b-chen"); pg.wait_for_selector(".pipe")
    vt = pg.inner_text("#view")
    check("old card with a stored phone/LINE: not shown, no call/LINE buttons", "0912" not in vt and "chen_sm" not in vt and pg.locator("a[href^='tel:'], a[href*='line.me'], #cpLine").count() == 0)
    go(pg, "#edit/b-chen"); pg.wait_for_selector("#f_job"); pg.fill("#f_job", "學生"); pg.click("#fSave"); pg.wait_for_timeout(1200)
    go(pg, "#new"); pg.wait_for_selector("#f_name"); check("register form: supplement (date-time, author, content) right under memo", pg.is_visible("#suppAt") and pg.is_visible("#suppBy") and pg.is_visible("#suppTxt") and pg.evaluate("document.querySelector('#f_memo').closest('label').nextElementSibling.id") == "suppBox")
    go(pg, "#edit/b-chen"); pg.wait_for_selector("#suppTxt"); pg.fill("#suppTxt", "儲存時一起補充"); pg.click("#fSave"); pg.wait_for_timeout(1500); go(pg, "#best/b-chen"); pg.wait_for_selector("#suppList"); pg.wait_for_timeout(800); check("edit form: text typed in supplement is saved by the main Save button", "儲存時一起補充" in pg.inner_text("#suppList"))
    oc = get("/bests/b-chen")
    check("old card still saves; old phone/LINE left untouched (harmless)", oc.get("job") == "學生" and oc.get("phone") == "0912-345-678" and oc.get("line") == "chen_sm", {k: oc.get(k) for k in ("job", "phone", "line")})
    go(pg, "#home"); pg.wait_for_timeout(800)
    pg.locator("[data-done='b-kim']").click(); pg.wait_for_timeout(800)
    check("next action 'done' clears it", get("/bests/b-kim")["nextAction"] == "" and "김하늘" not in sec("해야 할 일"))
    go(pg, "#best/b-wang"); pg.wait_for_selector("#suppList .sn", timeout=15000)
    lee = pg.locator("#suppList .sn", has_text="喜歡唱詩歌")
    check("someone else's supplement: shown with its author, no delete button for a non-admin", lee.count() == 1 and "보충자 李姊妹" in lee.inner_text() and lee.locator("[data-ndel]").count() == 0)
    # admin: master grants admin via REST (same as the production procedure), then CSV + church key
    go(pg, "#more"); pg.wait_for_selector("#adminBtn")
    check("QR device (not admin): More shows 'admin login', no admin tools, no sign-out", pg.locator("#invBtn").count() == 0 and pg.locator("#soBtn").count() == 0)
    req("PATCH", "/staff/" + uid + "?updateMask.fieldPaths=role", {"fields": {"role": {"stringValue": "admin"}}})
    pg.reload(); pg.wait_for_selector("#tabs:not([hidden])", timeout=20000)
    pg.click("a[data-tab=list]"); pg.wait_for_function("() => document.querySelectorAll('#listBox .item').length === 10", timeout=20000)   # data loaded
    pg.click("a[data-tab=more]"); pg.wait_for_selector("#csvBtn")
    try:
        with pg.expect_download(timeout=15000) as dl: pg.click("#csvBtn", no_wait_after=True, timeout=10000)
    except Exception as ex:
        pg.screenshot(path=f"{OUT}/_debug-csv.png")
        print("DEBUG", pg.evaluate("""() => { const W = document.documentElement.clientWidth; return {W, iw: innerWidth, sw: document.documentElement.scrollWidth, vv: visualViewport.width,
          off: [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > W + 1).slice(0, 12).map(e => e.tagName + '#' + e.id + '.' + e.className + ' r=' + Math.round(e.getBoundingClientRect().right) + ' w=' + Math.round(e.getBoundingClientRect().width))}; }"""), flush=True); raise
    path = dl.value.path(); csv = open(path, encoding="utf-8-sig", newline="").read()
    check("admin CSV export (10 BEST + header, nickname column)", csv.count("\r\n") == 10 and '"周恩惠","Grace"' in csv and all('"' + h + '"' in csv.splitlines()[0] for h in ("별명", "직업", "학교(과)", "학년")) and "전화" not in csv.splitlines()[0] and "LINE ID" not in csv.splitlines()[0] and "0912" not in csv, [csv.count("\r\n"), '"周恩惠","Grace"' in csv, "0912" in csv, csv.splitlines()[0]])
    check("CSV includes supplements (joined, with author)", '"보충"' in csv.splitlines()[0] and "김목자: 딸 유치원 근처에 삼" in csv and "李姊妹: 喜歡唱詩歌，可以邀請加入詩班" in csv)
    go(pg, "#best/b-wang"); pg.wait_for_selector("#suppList .sn [data-ndel]", timeout=15000)
    pg.locator("#suppList .sn", has_text="喜歡唱詩歌").locator("[data-ndel]").click(); pg.wait_for_timeout(1200)
    for _ in range(20):
        if lst("/bests/b-wang/notes") == []: break
        pg.wait_for_timeout(250)
    check("admin deletes anyone's supplement", lst("/bests/b-wang/notes") == [])
    go(pg, "#more"); pg.wait_for_selector("#invBtn")
    pg.click("#invBtn"); pg.wait_for_timeout(800)
    newcode = pg.inner_text("#invCode").strip(); link = pg.inner_text("#invLink").strip()
    check("admin changes church key (16 chars) + shows the new QR link", len(newcode) == 16 and get("/config/invite")["code"] == newcode and link == "http://127.0.0.1:5000/install.html?k=" + newcode, (newcode, link))
    KEY = newcode
    pg.screenshot(path=f"{OUT}/flow-7-more-ko.png")
    # Chinese
    pg.click("#langBtn"); go(pg, "#home"); pg.wait_for_timeout(800)
    zh = pg.inner_text("body")
    check("zh UI uses BEST label, no 새신자/新朋友 labels", "今天需要關懷的 BEST" in zh and "新朋友" not in zh and "새신자" not in zh)
    pg.screenshot(path=f"{OUT}/flow-2-home-zh.png")
    over = pg.evaluate("""() => { const W = innerWidth; return document.documentElement.scrollWidth > W + 1 ? [document.documentElement.scrollWidth, W, location.hash, [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > W + 1).slice(0, 6).map(e => e.tagName + '.' + e.className + ' r=' + Math.round(e.getBoundingClientRect().right))] : null; }""")
    check("no horizontal overflow at 390px", not over, over)
    # dark mode check
    small = pg.evaluate("[...document.querySelectorAll('input,select,textarea')].filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).length")
    go(pg, "#new"); pg.wait_for_selector("#f_name")
    small += pg.evaluate("[...document.querySelectorAll('input,select,textarea')].filter(e => e.type !== 'file' && parseFloat(getComputedStyle(e).fontSize) < 16).length")
    check("all inputs font-size >= 16px (no iOS zoom)", small == 0, small)
    sa = pg.evaluate("""() => { const out = {}; for (const ss of document.styleSheets) for (const r of ss.cssRules) { const m = r.cssText.match(/safe-area-inset-[a-z]+/g); if (m) out[r.selectorText] = [...new Set(m)].join(','); }
      out.viewport = document.querySelector('meta[name=viewport]').content; return out; }""")
    need = {"header.top": "top", "nav.tabs": "bottom", ".app": "left", ".fab": "bottom"}
    check("safe-area insets: viewport-fit=cover + header top, tab bar bottom, app left/right, FAB bottom", "viewport-fit=cover" in sa["viewport"] and all(v in sa.get(k, "") for k, v in need.items()) and "right" in sa.get(".app", ""), sa)
    # ---------- full bilingual tour: every screen in both languages, untranslated-text detector ----------
    DATA = ["陳小明", "林美華", "張志豪", "王淑芬", "黃建國", "吳佳蓉", "김하늘", "劉家豪", "蔡雅婷", "李姊妹", "박집사", "김목자", "周恩惠", "Grace", "Ming", "하늘이", "동역자", "同工", "設計師", "台灣師大(美術系)", "研一", "學生", "딸 유치원 근처에 삼", "喜歡唱詩歌，可以邀請加入詩班",
            "주중 LINE으로 안부", "家庭探訪，一起吃晚餐", "工作穩定", "台北市 信義區", "先生、女兒(5歲)", "女兒身體健康", "喜歡詩歌",
            "LINE로 환영 인사, 다음 주일 다시 오기로", "딸의 건강", "주일 예배 후 식사 초대", "kim-sub@example.com"]
    DATA += [d[0] for d in DATA] + ["Tour", "T"]   # avatar initials are data too
    HANGUL, HAN = re.compile("[\uac00-\ud7a3]"), re.compile("[\u4e00-\u9fff]")
    JS_TEXTS = """() => { const out = []; const vis = (el) => el && (el.tagName === 'OPTION' || el.getClientRects().length > 0);
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
      while ((n = w.nextNode())) { const s = n.textContent.trim(); if (s && vis(n.parentElement) && !n.parentElement.closest('#langBtn')) out.push(s); }
      document.querySelectorAll('[placeholder]').forEach((e) => out.push(e.placeholder)); out.push(document.title); return out; }"""
    def leftovers(page, lang):
        bad = []
        for s in page.evaluate(JS_TEXTS):
            x = s
            for d in sorted(DATA, key=len, reverse=True): x = x.replace(d, "")
            if (lang == "zh" and HANGUL.search(x)) or (lang == "ko" and HAN.search(x)): bad.append(s)
        return bad
    def setlang(page, lang): page.evaluate(f"localStorage.setItem('best.lang', '{lang}')")
    zoom_bad = []
    for lang in ("ko", "zh"):
        bad_all = {}
        go(pg, "#home"); pg.wait_for_selector(".stats")
        if pg.evaluate("document.documentElement.lang").startswith("zh") != (lang == "zh"): pg.click("#langBtn")
        screens = [("home", "#home", ".stats"), ("list", "#list", "#listBox"), ("detail", "#best/" + bid, ".pipe"), ("register", "#new", "#f_name"),
                   ("attendance", "#att", "#attDay"), ("more", "#more", "#csvBtn")]
        for name, h, sel in screens:
            go(pg, h)
            try: pg.wait_for_selector(sel, timeout=15000)
            except Exception:
                pg.screenshot(path=f"{OUT}/_debug-{lang}-{name}.png"); print("DEBUG-ERRS", errors[-6:], flush=True); print("DEBUG", name, pg.evaluate("[window.__me && window.__me(), Object.keys(localStorage), location.href, document.activeElement && document.activeElement.outerHTML.slice(0,120), document.querySelector('#view').innerText.slice(0,200)]"), flush=True); raise
            pg.wait_for_timeout(600)
            if name == "detail":
                pg.click("#addLogBtn"); pg.locator("details").evaluate("d => d.open = true")
            if name == "attendance":
                pg.fill("#attDay", sun(0)); pg.dispatch_event("#attDay", "change"); pg.wait_for_timeout(400)
            pg.screenshot(path=f"{OUT}/{lang}-{name}.png"); pg.screenshot(path=f"{OUT}/{lang}-{name}-full.png", full_page=True)
            b_ = leftovers(pg, lang)
            if b_: bad_all[name] = b_
            if name == "register":   # crop dialog text too (O62)
                pg.set_input_files("#f_photo", files=[CROPIMG]); pg.wait_for_selector("#cropDlg"); pg.wait_for_timeout(300)
                pg.screenshot(path=f"{OUT}/{lang}-crop.png"); b_ = leftovers(pg, lang)
                if b_: bad_all["crop"] = b_
                pg.click("#cropCancel"); pg.wait_for_selector("#cropDlg", state="detached")
            z = pg.evaluate("[document.documentElement.scrollWidth, innerWidth, Math.round(visualViewport.width)]")
            if z[0] > z[1] + 1 or z[2] < z[1] - 1: zoom_bad.append((lang, name, z))
        pg.goto("http://127.0.0.1:5000/install.html"); pg.wait_for_selector("ol"); pg.wait_for_timeout(300)
        pg.screenshot(path=f"{OUT}/{lang}-install.png"); pg.screenshot(path=f"{OUT}/{lang}-install-full.png", full_page=True)
        b_ = leftovers(pg, lang)
        if b_: bad_all["install"] = b_
        go(pg, "#more"); pg.wait_for_selector("#csvBtn")
        with pg.expect_download() as dl: pg.click("#csvBtn", no_wait_after=True)
        head = open(dl.value.path(), encoding="utf-8-sig", newline="").read().split("\r\n")[0]
        if (lang == "zh" and HANGUL.search(head)) or (lang == "ko" and HAN.search(head)): bad_all["csv-header"] = [head]
        # fresh device: no-key screen, wrong code typed (fallback entry), right code typed -> joined home with the optional name prompt
        c2 = br.new_context(**DEV); p2 = c2.new_page()
        p2.add_init_script(f"localStorage.setItem('best.lang', '{lang}')")
        p2.goto("http://127.0.0.1:5000/"); p2.wait_for_selector("#noKey")
        p2.screenshot(path=f"{OUT}/{lang}-nokey.png"); b_ = leftovers(p2, lang)
        if b_: bad_all["nokey"] = b_
        p2.click("#codeLink"); p2.fill("#kCode", "NOPE0000NOPE0000"); p2.click("#kBtn"); p2.wait_for_selector("#codeErr", timeout=20000)
        p2.screenshot(path=f"{OUT}/{lang}-nokey-error.png"); b_ = leftovers(p2, lang)
        if b_: bad_all["nokey-error"] = b_
        p2.click("#codeLink"); p2.fill("#kCode", KEY.lower()); p2.click("#kBtn"); p2.wait_for_selector("#tabs:not([hidden])", timeout=20000)
        p2.wait_for_selector("#askNm"); p2.wait_for_timeout(800)
        joined_ok = p2.evaluate("window.__me().anon") and get("/staff/" + p2.evaluate("window.__me().uid"))["name"] == ("동역자" if lang == "ko" else "同工")
        p2.screenshot(path=f"{OUT}/{lang}-joined-home.png"); b_ = leftovers(p2, lang)
        if b_: bad_all["joined-home"] = b_
        if not joined_ok: bad_all["joined"] = ["typed church code did not join with the default name"]
        c2.close()
        check(f"{lang}: every screen fully {('Korean' if lang == 'ko' else 'Traditional Chinese')} (home/list/detail+log form/register/attendance/more/install/sign-in/invite+error/CSV header)", not bad_all, bad_all)
    setlang(pg, "ko")
    check("every screen: no horizontal overflow / no unwanted zoom (both languages)", not zoom_bad, zoom_bad)
    # deactivate: admin deactivates 박집사 -> that staff has no access (rules test covers), UI shows inactive
    go(pg, "#more"); pg.wait_for_selector("[data-act='staff-park']")
    pg.click("[data-act='staff-park']"); pg.wait_for_timeout(800)
    check("admin deactivates a staff member", get("/staff/staff-park")["active"] is False)
    # admin keeps working through Google sign-in from the More tab
    c3 = br.new_context(**DEV); p3 = c3.new_page(); p3.on("console", lambda m: errors.append("c3:" + m.text) if m.type in ("error", "warning") else None)
    p3.goto(f"http://127.0.0.1:5000/?k={KEY}"); W(p3, "#tabs:not([hidden])", timeout=20000)
    p3.goto("http://127.0.0.1:5000/#more"); W(p3, "#adminBtn")
    p3.evaluate("window.__emuSignIn('pastor-sub', 'Pastor')"); p3.wait_for_function("() => window.__me() && !window.__me().anon", timeout=20000)
    try: W(p3, "#tabs:not([hidden])", timeout=20000)
    except Exception:
        print("DEBUG-C3", p3.evaluate("[window.__me(), Object.keys(localStorage), document.querySelector('#view').innerText.slice(0, 300)]"), errors[-5:], flush=True); raise
    a_uid = p3.evaluate("window.__me().uid")
    for _ in range(40):
        try:
            if get("/staff/" + a_uid).get("name"): break
        except Exception: pass
        p3.wait_for_timeout(250)
    req("PATCH", "/staff/" + a_uid + "?updateMask.fieldPaths=role", {"fields": {"role": {"stringValue": "admin"}}})
    p3.reload(); p3.goto("http://127.0.0.1:5000/#more"); W(p3, "#invBtn", timeout=20000)
    check("admin Google sign-in from More: admin tools + sign-out shown", p3.is_visible("#csvBtn") and p3.is_visible("#soBtn") and "pastor-sub@example.com" in p3.inner_text("#view"))
    p3.screenshot(path=f"{OUT}/flow-8-admin-google-ko.png")
    p3.click("#soBtn"); p3.wait_for_function("() => window.__me() && window.__me().anon", timeout=20000); W(p3, "#tabs:not([hidden])", timeout=20000)
    check("admin sign-out: device falls back to the church key (anonymous staff)", get("/staff/" + p3.evaluate("window.__me().uid"))["role"] == "staff")
    c3.close()
    br.close()
emu_noise = [e for e in errors if "127.0.0.1:8080/google.firestore.v1.Firestore/" in e and "access control checks" in e]
real = [e for e in errors if "favicon" not in e and e not in emu_noise
        and not (ENGINE == "webkit" and emu_noise and ("Could not reach Cloud Firestore backend" in e))]
if emu_noise: print(f"note: {len(emu_noise)} WebKit<->local-emulator channel aborts on page navigation ('access control checks') ignored", flush=True)
check("no console errors", not real, real[:5])
fails = [n for n, ok in results if not ok]
print(f"\nE2E: {len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
