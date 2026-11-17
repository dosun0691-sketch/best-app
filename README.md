# BEST 돌봄 · BEST 關懷 — newcomer (BEST) care app for staff

Live: https://ourfamily-best-1117.web.app  (Firebase project `ourfamily-best-1117`, Firestore asia-east1, Spark plan)
Android: TWA package `tw.ourfamily.best` (android/), signed APK `android/best-app.apk` (git-ignored).

## Files
- `public/index.html` — the whole app (ko / 繁中 toggle, no login: church QR key + Firebase Anonymous auth; Google sign-in only for the admin; Firestore).
- `public/church-logo.png` — 我們家教會 logo (header, no-key screen, install page, QR card). The BEST app icon is separate and unchanged.
- `firestore.rules` — only ACTIVE staff can read/write; invite code never readable by clients.
- `test/rules.test.mjs` — rules tests (emulator). `test/e2e.py` — browser E2E against emulators (sample data, writes shots/).
- `invite-code.txt` — current church key + the QR link (git-ignored). NEVER commit the key or put it in the public repo, the APK or release notes.
- `qrwork/` (git-ignored) — QR card: `card.html` + `qr.png` -> rendered to the Desktop as `BEST 앱 설치 QR.png`.

## Access: no login, the QR is the key (O27, 2026-11-17)
- Only the church's staff (同工) install the app. The QR on the card opens `https://ourfamily-best-1117.web.app/install.html?k=<KEY>`.
- Any page opened with `?k=` stores the key on the device (localStorage `best.key` + cookie `best_key`) and removes it from the address bar.
- The app then signs in with **Firebase Anonymous auth** (enabled in the project; one uid per install) and joins once: it writes
  `staffKeys/{uid}.code = key` + `staff/{uid}` {name '동역자'/'同工', role staff, active}. The rules accept that only when the key equals
  `config/invite.code` (never client-readable). Every QR device is then full staff (read + create/update BESTs, logs, supplements, attendance).
- First open asks only for an optional name (skippable; editable in 더보기 / 更多). Without a key the app shows only
  "교회 QR코드로 열어 주세요 / 請用教會的 QR 碼開啟" with a small "enter church code" fallback; Firestore stays closed.
- Admin: the existing Google admin account signs in from 더보기 → 「관리자 로그인 (Google)」 (also a small link on the no-key screen).
- **iPhone**: Safari and the home-screen app do NOT share storage (firt.dev/notes/pwa-ios: "Storage shared with Browser ❌"). So on iPhone
  Safari (not yet on the home screen) the app keeps `?k=KEY` in the URL and links NO web manifest; without a manifest, "Add to Home Screen"
  saves the current page URL, so the home-screen app starts with the key. install.html's 「BEST 열기」 button opens `./?k=KEY` for that
  step. Extra fallback: the `best_key` cookie (iOS 17.2+ copies cookies into a newly added home-screen app). If the home-screen app still
  opens without a key it shows the "scan the QR" screen: delete the icon, scan the QR again, add again (install.html note says so).
- **Android TWA**: the APK start URL has no key; the TWA shares storage with the Chrome profile, so a key stored when the QR was opened in
  Chrome carries over. If not (other default browser / cleared data), the app says "scan the QR once": the QR link is on the verified host
  (assetlinks + `autoVerify` intent filter for the whole host), so it opens inside the installed app and stores the key there.
  No APK rebuild was needed (start URL unchanged).

### Rotate the key (lost card, someone left)
1. New random key (12-32 chars A-Z0-9; the app makes 16): admin → 더보기 → 「교회 코드(QR) 바꾸기」 (shows the new code + link once), or REST:
   `curl -X PATCH ... -d '{"fields":{"code":{"stringValue":"<KEY>"}}}' ".../documents/config/invite?updateMask.fieldPaths=code"`.
2. Save it in `invite-code.txt`, regenerate `qrwork/qr.png` from the new link, re-render the card, reprint.
3. **Old installs keep access** (they already joined). To remove a device or person: admin → 더보기 → staff list → 「사용 중지」 (deactivate).
   A deactivated device that later gets the NEW key (scans the new card) can join again as a new device - rotate the key and deactivate together.

## Data
- `staff/{uid}` {name, active, role: staff|admin, joinedAt}
- `staffKeys/{uid}` {code} — church key presented at join (write-only)
- `config/invite` {code} — church key (no client read; admin may replace from the app)
- `bests/{id}` registration card (name, nick<=20, photo, gender, age, job/school/grade<=40, area, firstVisit, invitedBy, faith, family, memo, prayer) + stage, stageHistory, cls[5] (BEST class weeks), caretaker, lastContact, nextAction/nextDue
- `bests/{id}/logs/{id}` contact/visit log {date, method, content, prayer, next, due, by}
- `bests/{id}/notes/{id}` supplement under the memo (보충 / 補充) {text<=500, by, byName, at} — append-only; author or admin deletes
- phone / LINE ID were removed from the card (2026-11-17): never written on new cards, old stored values are hidden and may only stay unchanged or be removed (rules `legacyOk`).
- `attendance/{YYYY-MM-DD}` {ids:[best ids present]}

## Admin (set by master via REST — the app never grants admin)
```bash
TOKEN=$(node -e "console.log(require(process.env.USERPROFILE+'/.config/configstore/firebase-tools.json').tokens.access_token)")  # run any firebase command first to refresh
# find the uid: list staff
curl -s -H "Authorization: Bearer $TOKEN" "https://firestore.googleapis.com/v1/projects/ourfamily-best-1117/databases/(default)/documents/staff"
# make admin
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"fields":{"role":{"stringValue":"admin"}}}' \
  "https://firestore.googleapis.com/v1/projects/ourfamily-best-1117/databases/(default)/documents/staff/<UID>?updateMask.fieldPaths=role"
```
Use `"staff"` to remove admin. Reset the church key the same way on `config/invite` (field `code`, 12-32 chars A-Z0-9) — see "Rotate the key".

## iPhone / Android
- iPhone: QR → Safari → 「BEST 열기」 → Share → 홈 화면에 추가 / 加入主畫面 (PWA; guide at /install.html, ko + zh). Admin Google sign-in uses redirect
  in the iOS home-screen app (authDomain = this hosting domain, first-party /__/auth/handler); popup elsewhere.
- Android: TWA APK (below). install.html has `const APK_URL = ''` — set it to the published APK URL (Spark Hosting cannot serve .apk).

## Tests
```bash
# JDK 21+ required by the emulators (portable copy: ~/.jdks/jdk-21*)
firebase emulators:exec --only firestore --project demo-best "cd test && npm test"
firebase emulators:exec --only auth,firestore,hosting --project demo-best "python -I test/e2e.py edge"     # Chromium (Android TWA engine)
firebase emulators:exec --only auth,firestore,hosting --project demo-best "python -I test/e2e.py webkit"   # WebKit, iPhone 14 (python -m playwright install webkit)
python -I test/live_webkit.py   # live no-key screen + install page in WebKit
python -I test/live_smoke.py    # live: no-key, wrong key, right key (creates ONE test device - delete staff/{uid}, staffKeys/{uid} and the anonymous auth user afterwards)
```

## Deploy / Android
- `firebase deploy --only hosting,firestore:rules`
- APK: in android/: `gradlew.bat assembleRelease` (JAVA_HOME=JDK 17, ANDROID_HOME=~/.bubblewrap/android_sdk), then zipalign + apksigner
  (build-tools 34.0.0) with android/android.keystore (alias best, password in android/keystore-info.txt — never commit; backup kept outside the repo).
  Bump versionCode in android/app/build.gradle + twa-manifest.json for updates. assetlinks: public/.well-known/assetlinks.json.
