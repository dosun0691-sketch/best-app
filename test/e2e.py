
# E2E against Firebase emulators (auth+firestore+hosting). Run via: firebase emulators:exec --only auth,firestore,hosting --project demo-best "python -I test/e2e.py"
import json, sys, urllib.request, datetime, os
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
put("/config/invite", {"code": "TESTC0DE"})
put("/staff/staff-lee", {"name": "李姊妹", "active": True, "role": "staff"})
put("/staff/staff-park", {"name": "박집사", "active": True, "role": "staff"})
base = {"createdAt": datetime.datetime.utcnow(), "updatedAt": datetime.datetime.utcnow(), "cls": [False]*5, "lastContact": "", "nextAction": "", "nextDue": "", "createdBy": "staff-lee", "updatedBy": "staff-lee"}
seed = {
 "b-chen": {"name": "陳小明", "firstVisit": sun(0), "stage": "first", "caretaker": "staff-lee", "phone": "0912-345-678", "line": "chen_sm"},
 "b-lin": {"name": "林美華", "firstVisit": sun(1), "stage": "first", "caretaker": "staff-park"},
 "b-zhang": {"name": "張志豪", "firstVisit": sun(6), "stage": "revisit", "caretaker": "staff-lee", "lastContact": sun(4)},
 "b-wang": {"name": "王淑芬", "firstVisit": sun(9), "stage": "class", "cls": [True, True, True, False, False], "lastContact": sun(1), "caretaker": "staff-park"},
 "b-huang": {"name": "黃建國", "firstVisit": sun(9), "stage": "group", "lastContact": sun(2)},
 "b-wu": {"name": "吳佳蓉", "firstVisit": sun(9), "stage": "welcome", "lastContact": sun(8)},
 "b-kim": {"name": "김하늘", "firstVisit": sun(2), "stage": "welcome", "lastContact": sun(2), "nextAction": "주중 LINE으로 안부", "nextDue": (today - datetime.timedelta(days=2)).isoformat(), "caretaker": "staff-park"},
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
put("/bests/b-wang/logs/l1", {"date": sun(1), "method": "visit", "content": "家庭探訪，一起吃晚餐", "prayer": "工作穩定", "by": "staff-park"})

errors = []
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
    _c = br.new_context(**DEV); _p = _c.new_page(); _p.goto("http://127.0.0.1:5000/install.html")
    print("css viewport:", _p.evaluate("[innerWidth, innerHeight, Math.round(devicePixelRatio*100)/100, navigator.userAgent]"), flush=True); _c.close()
    ctx = br.new_context(**DEV, locale="ko-KR", accept_downloads=True)
    pg = ctx.new_page()
    if ENGINE == "webkit": ZPAGE.append(pg)
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://127.0.0.1:5000/")
    pg.wait_for_selector("#gBtn")
    check("logged-out: only sign-in screen (no tabs)", pg.is_hidden("#tabs") and pg.is_visible("#gBtn"))
    pg.screenshot(path=f"{OUT}/flow-0-signin-ko.png")
    pg.evaluate("window.__emuSignIn('kim-sub', '김목자')")
    pg.wait_for_selector("#jCode")
    check("signed-in non-staff: invite-code screen, no data", pg.is_hidden("#tabs"))
    pg.fill("#jCode", "WRONG999"); pg.click("#jBtn"); pg.wait_for_timeout(1500)
    check("wrong invite code rejected", pg.is_visible("#jCode") and "초대 코드가 맞지 않습니다" in pg.inner_text("body"))
    pg.screenshot(path=f"{OUT}/flow-1-join-ko.png")
    pg.fill("#jCode", "testc0de"); pg.click("#jBtn")
    pg.wait_for_selector("#tabs:not([hidden])")
    me = [x for x in lst("/staff") if x[1].get("name") == "김목자"]
    check("joined as plain staff (not admin)", me and me[0][1]["role"] == "staff", me and me[0][1])
    uid = me[0][0]
    # master grants admin via REST (same as production procedure)
    req("PATCH", "/staff/" + uid + "?updateMask.fieldPaths=role", {"fields": {"role": {"stringValue": "admin"}}})
    pg.reload(); pg.wait_for_selector("text=오늘 돌봐야 할 BEST")
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
    pg.fill("#f_name", "周恩惠 Grace"); pg.select_option("#f_gender", "f"); pg.select_option("#f_age", "30")
    pg.fill("#f_phone", "0987-654-321"); pg.fill("#f_line", "grace_chou"); pg.fill("#f_area", "台北市 信義區")
    pg.fill("#f_invitedBy", "王淑芬"); pg.select_option("#f_faith", "moved"); pg.fill("#f_family", "先生、女兒(5歲)")
    pg.fill("#f_prayer", "女兒身體健康"); pg.fill("#f_memo", "喜歡詩歌")
    pg.select_option("#f_caretaker", "staff-lee")
    pg.set_input_files("#f_photo", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "icon-512.png"))
    pg.wait_for_timeout(500)
    pg.screenshot(path=f"{OUT}/flow-3-register-ko.png")
    pg.click("#fSave"); pg.wait_for_selector(".pipe"); pg.wait_for_timeout(500)
    bid = pg.evaluate("location.hash").split("/")[1]
    b = get("/bests/" + bid)
    check("BEST registered with all fields", b["name"] == "周恩惠 Grace" and b["phone"] == "0987-654-321" and b["faith"] == "moved" and b["photo"].startswith("data:image/jpeg") and len(b["photo"]) < 300000, {k: (v if k != "photo" else len(v)) for k, v in b.items() if k not in ("createdAt", "updatedAt")})
    check("caretaker assigned at registration", b["caretaker"] == "staff-lee")
    pg.select_option("#careSel", "staff-park"); pg.wait_for_timeout(800)
    check("caretaker re-assigned from detail", get("/bests/" + bid)["caretaker"] == "staff-park")
    pg.click("[data-st=welcome]"); pg.wait_for_timeout(800)
    pg.click("[data-st=revisit]"); pg.wait_for_timeout(800)
    pg.check("[data-wk='0']"); pg.wait_for_timeout(800)
    b = get("/bests/" + bid)
    check("stage moved + history kept", b["stage"] == "revisit" and [x["s"] for x in b["stageHistory"]] == ["first", "welcome", "revisit"], b["stageHistory"])
    check("BEST class week 1 checked", b["cls"] == [True, False, False, False, False])
    pg.click("#addLogBtn"); pg.select_option("#l_method", "line")
    pg.fill("#l_content", "LINE로 환영 인사, 다음 주일 다시 오기로"); pg.fill("#l_prayer", "딸의 건강"); pg.fill("#l_next", "주일 예배 후 식사 초대")
    pg.fill("#l_due", T); pg.click("#l_save"); pg.wait_for_timeout(1200)
    logs = lst("/bests/" + bid + "/logs"); b = get("/bests/" + bid)
    check("contact log saved + lastContact/nextAction updated", len(logs) == 1 and logs[0][1]["method"] == "line" and b["lastContact"] == T and b["nextDue"] == T, (logs, b["lastContact"], b["nextAction"]))
    pg.wait_for_selector(".log")
    pg.screenshot(path=f"{OUT}/flow-4-detail-ko.png")
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
    pg.select_option("#careSel", ""); pg.fill("#q", "0912"); pg.wait_for_timeout(200); n_q = pg.locator("#listBox .item").count()
    check("list: all 10 / stage first 2 / caretaker 박집사 4 / search phone 1", (n_all, n_first, n_park, n_q) == (10, 2, 4, 1), (n_all, n_first, n_park, n_q))
    pg.fill("#q", ""); pg.wait_for_timeout(200)
    pg.screenshot(path=f"{OUT}/flow-6-list-ko.png")
    # tel: link + done button
    pg.goto("http://127.0.0.1:5000/#best/b-chen"); pg.wait_for_selector(".pipe")
    check("tap phone -> tel: link", pg.get_attribute("a[href^='tel:']", "href") == "tel:0912345678")
    pg.goto("http://127.0.0.1:5000/#home"); pg.wait_for_timeout(800)
    pg.locator("[data-done='b-kim']").click(); pg.wait_for_timeout(800)
    check("next action 'done' clears it", get("/bests/b-kim")["nextAction"] == "" and "김하늘" not in sec("해야 할 일"))
    # admin: csv + invite
    pg.click("a[data-tab=more]"); pg.wait_for_selector("#csvBtn")
    try:
        with pg.expect_download(timeout=15000) as dl: pg.click("#csvBtn", no_wait_after=True, timeout=10000)
    except Exception as ex:
        pg.screenshot(path=f"{OUT}/_debug-csv.png")
        print("DEBUG", pg.evaluate("""() => { const W = document.documentElement.clientWidth; return {W, iw: innerWidth, sw: document.documentElement.scrollWidth, vv: visualViewport.width,
          off: [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > W + 1).slice(0, 12).map(e => e.tagName + '#' + e.id + '.' + e.className + ' r=' + Math.round(e.getBoundingClientRect().right) + ' w=' + Math.round(e.getBoundingClientRect().width))}; }"""), flush=True); raise
    path = dl.value.path(); csv = open(path, encoding="utf-8-sig", newline="").read()
    check("admin CSV export (10 BEST + header)", csv.count("\r\n") == 10 and "周恩惠 Grace" in csv, csv.splitlines()[0])
    pg.click("#invBtn"); pg.wait_for_timeout(800)
    newcode = pg.inner_text("#invOut").split(":")[-1].strip()
    check("admin changes invite code", len(newcode) == 8 and get("/config/invite")["code"] == newcode, newcode)
    pg.screenshot(path=f"{OUT}/flow-7-more-ko.png")
    # Chinese
    pg.click("#langBtn"); pg.goto("http://127.0.0.1:5000/#home"); pg.wait_for_timeout(800)
    zh = pg.inner_text("body")
    check("zh UI uses BEST label, no 새신자/新朋友 labels", "今天需要關懷的 BEST" in zh and "新朋友" not in zh and "새신자" not in zh)
    pg.screenshot(path=f"{OUT}/flow-2-home-zh.png")
    over = pg.evaluate("""() => { const W = innerWidth; return document.documentElement.scrollWidth > W + 1 ? [document.documentElement.scrollWidth, W, location.hash, [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > W + 1).slice(0, 6).map(e => e.tagName + '.' + e.className + ' r=' + Math.round(e.getBoundingClientRect().right))] : null; }""")
    check("no horizontal overflow at 390px", not over, over)
    # dark mode check
    small = pg.evaluate("[...document.querySelectorAll('input,select,textarea')].filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).length")
    pg.goto("http://127.0.0.1:5000/#new"); pg.wait_for_selector("#f_name")
    small += pg.evaluate("[...document.querySelectorAll('input,select,textarea')].filter(e => e.type !== 'file' && parseFloat(getComputedStyle(e).fontSize) < 16).length")
    check("all inputs font-size >= 16px (no iOS zoom)", small == 0, small)
    sa = pg.evaluate("""() => { const out = {}; for (const ss of document.styleSheets) for (const r of ss.cssRules) { const m = r.cssText.match(/safe-area-inset-[a-z]+/g); if (m) out[r.selectorText] = [...new Set(m)].join(','); }
      out.viewport = document.querySelector('meta[name=viewport]').content; return out; }""")
    need = {"header.top": "top", "nav.tabs": "bottom", ".app": "left", ".fab": "bottom"}
    check("safe-area insets: viewport-fit=cover + header top, tab bar bottom, app left/right, FAB bottom", "viewport-fit=cover" in sa["viewport"] and all(v in sa.get(k, "") for k, v in need.items()) and "right" in sa.get(".app", ""), sa)
    # ---------- full bilingual tour: every screen in both languages, untranslated-text detector ----------
    DATA = ["陳小明", "林美華", "張志豪", "王淑芬", "黃建國", "吳佳蓉", "김하늘", "劉家豪", "蔡雅婷", "李姊妹", "박집사", "김목자", "周恩惠 Grace",
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
        pg.goto("http://127.0.0.1:5000/#home"); pg.wait_for_selector(".stats")
        if pg.evaluate("document.documentElement.lang").startswith("zh") != (lang == "zh"): pg.click("#langBtn")
        screens = [("home", "#home", ".stats"), ("list", "#list", "#listBox"), ("detail", "#best/" + bid, ".pipe"), ("register", "#new", "#f_name"),
                   ("attendance", "#att", "#attDay"), ("more", "#more", "#csvBtn")]
        for name, h, sel in screens:
            pg.goto("http://127.0.0.1:5000/" + h)
            try: pg.wait_for_selector(sel, timeout=15000)
            except Exception:
                pg.screenshot(path=f"{OUT}/_debug-{lang}-{name}.png"); print("DEBUG-ERRS", errors[-6:], flush=True); print("DEBUG", name, pg.evaluate("[location.href, document.activeElement && document.activeElement.outerHTML.slice(0,120), document.querySelector('#view').innerText.slice(0,200)]"), flush=True); raise
            pg.wait_for_timeout(600)
            if name == "detail":
                pg.click("#addLogBtn"); pg.locator("details").evaluate("d => d.open = true")
            if name == "attendance":
                pg.fill("#attDay", sun(0)); pg.dispatch_event("#attDay", "change"); pg.wait_for_timeout(400)
            pg.screenshot(path=f"{OUT}/{lang}-{name}.png"); pg.screenshot(path=f"{OUT}/{lang}-{name}-full.png", full_page=True)
            b_ = leftovers(pg, lang)
            if b_: bad_all[name] = b_
            z = pg.evaluate("[document.documentElement.scrollWidth, innerWidth, Math.round(visualViewport.width)]")
            if z[0] > z[1] + 1 or z[2] < z[1] - 1: zoom_bad.append((lang, name, z))
        pg.goto("http://127.0.0.1:5000/install.html"); pg.wait_for_selector("ol"); pg.wait_for_timeout(300)
        pg.screenshot(path=f"{OUT}/{lang}-install.png"); pg.screenshot(path=f"{OUT}/{lang}-install-full.png", full_page=True)
        b_ = leftovers(pg, lang)
        if b_: bad_all["install"] = b_
        pg.goto("http://127.0.0.1:5000/#more"); pg.wait_for_selector("#csvBtn")
        with pg.expect_download() as dl: pg.click("#csvBtn", no_wait_after=True)
        head = open(dl.value.path(), encoding="utf-8-sig", newline="").read().split("\r\n")[0]
        if (lang == "zh" and HANGUL.search(head)) or (lang == "ko" and HAN.search(head)): bad_all["csv-header"] = [head]
        # logged-out screens in a fresh context: sign-in, invite code + wrong-code message
        c2 = br.new_context(**DEV); p2 = c2.new_page()
        p2.add_init_script(f"localStorage.setItem('best.lang', '{lang}')")
        p2.goto("http://127.0.0.1:5000/"); p2.wait_for_selector("#gBtn")
        p2.screenshot(path=f"{OUT}/{lang}-signin.png"); b_ = leftovers(p2, lang)
        if b_: bad_all["signin"] = b_
        p2.evaluate(f"window.__emuSignIn('tour-{lang}', 'Tour')"); p2.wait_for_selector("#jCode")
        p2.fill("#jCode", "NOPE0000"); p2.click("#jBtn"); p2.wait_for_selector(".toast")
        p2.screenshot(path=f"{OUT}/{lang}-join.png"); b_ = leftovers(p2, lang)
        if b_: bad_all["join"] = b_
        c2.close()
        check(f"{lang}: every screen fully {('Korean' if lang == 'ko' else 'Traditional Chinese')} (home/list/detail+log form/register/attendance/more/install/sign-in/invite+error/CSV header)", not bad_all, bad_all)
    setlang(pg, "ko")
    check("every screen: no horizontal overflow / no unwanted zoom (both languages)", not zoom_bad, zoom_bad)
    # deactivate: admin deactivates 박집사 -> that staff has no access (rules test covers), UI shows inactive
    pg.goto("http://127.0.0.1:5000/#more"); pg.wait_for_selector("[data-act='staff-park']")
    pg.click("[data-act='staff-park']"); pg.wait_for_timeout(800)
    check("admin deactivates a staff member", get("/staff/staff-park")["active"] is False)
    pg.click("#soBtn"); pg.wait_for_selector("#gBtn")
    check("sign-out returns to sign-in screen", pg.is_hidden("#tabs"))
    br.close()
emu_noise = [e for e in errors if "127.0.0.1:8080/google.firestore.v1.Firestore/" in e and "access control checks" in e]
real = [e for e in errors if "favicon" not in e and e not in emu_noise
        and not (ENGINE == "webkit" and emu_noise and ("Could not reach Cloud Firestore backend" in e))]
if emu_noise: print(f"note: {len(emu_noise)} WebKit<->local-emulator channel aborts on page navigation ('access control checks') ignored", flush=True)
check("no console errors", not real, real[:5])
fails = [n for n, ok in results if not ok]
print(f"\nE2E: {len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
