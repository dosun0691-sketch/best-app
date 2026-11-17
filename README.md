# BEST 돌봄 · BEST 關懷 — newcomer (BEST) care app for staff

Live: https://ourfamily-best-1117.web.app  (Firebase project `ourfamily-best-1117`, Firestore asia-east1, Spark plan)
Android: TWA package `tw.ourfamily.best` (android/), signed APK `android/best-app.apk` (git-ignored).

## Files
- `public/index.html` — the whole app (ko / 繁中 toggle, Google sign-in, Firestore).
- `firestore.rules` — only ACTIVE staff can read/write; invite code never readable by clients.
- `test/rules.test.mjs` — rules tests (emulator). `test/e2e.py` — browser E2E against emulators (sample data, writes shots/).
- `invite-code.txt` — current invite code (git-ignored).

## Data
- `staff/{uid}` {name, active, role: staff|admin, joinedAt}
- `staffKeys/{uid}` {code} — code typed at join (write-only)
- `config/invite` {code} — invite code (no client read; admin may replace from the app)
- `bests/{id}` registration card + stage, stageHistory, cls[5] (BEST class weeks), caretaker, lastContact, nextAction/nextDue
- `bests/{id}/logs/{id}` contact/visit log {date, method, content, prayer, next, due, by}
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
Use `"staff"` to remove admin. Reset the invite code the same way on `config/invite` (field `code`, 8 chars A-Z0-9), or from the app (admin → 더보기 / 更多).

## Tests
```bash
# JDK 21+ required by the emulators (portable copy: ~/.jdks/jdk-21*)
firebase emulators:exec --only firestore --project demo-best "cd test && npm test"
firebase emulators:exec --only auth,firestore,hosting --project demo-best "python -I test/e2e.py"
```

## Deploy / Android
- `firebase deploy --only hosting,firestore:rules`
- APK: in android/: `gradlew.bat assembleRelease` (JAVA_HOME=JDK 17, ANDROID_HOME=~/.bubblewrap/android_sdk), then zipalign + apksigner
  (build-tools 34.0.0) with android/android.keystore (alias best, password in android/keystore-info.txt — never commit; backup kept outside the repo).
  Bump versionCode in android/app/build.gradle + twa-manifest.json for updates. assetlinks: public/.well-known/assetlinks.json.
