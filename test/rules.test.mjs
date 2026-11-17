// Firestore security rules tests — run: cd best-app && firebase emulators:exec --only firestore "cd test && npm test"
import { test, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { initializeTestEnvironment, assertFails, assertSucceeds } from '@firebase/rules-unit-testing';
import { doc, getDoc, getDocs, setDoc, updateDoc, deleteDoc, collection, writeBatch, serverTimestamp, arrayUnion, setLogLevel } from 'firebase/firestore';
setLogLevel('silent');

let env;
const CODE = 'TESTC0DE2026KEYX';   // church key (12-32 chars A-Z0-9)
before(async () => {
  env = await initializeTestEnvironment({
    projectId: 'demo-best',
    firestore: { rules: readFileSync(new URL('../firestore.rules', import.meta.url), 'utf8'), host: '127.0.0.1', port: 8080 },
  });
});
after(async () => { await env.cleanup(); });
beforeEach(async () => {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await setDoc(doc(db, 'config/invite'), { code: CODE });
    await setDoc(doc(db, 'staff/staff1'), { name: 'Staff One', active: true, role: 'staff' });
    await setDoc(doc(db, 'staff/admin1'), { name: 'Admin', active: true, role: 'admin' });
    await setDoc(doc(db, 'staff/gone1'), { name: 'Gone', active: false, role: 'staff' });
    await setDoc(doc(db, 'bests/b1'), { name: 'BEST A', stage: 'first' });
    await setDoc(doc(db, 'bests/b1/logs/l1'), { date: '2026-11-16', method: 'phone', by: 'staff1' });
    await setDoc(doc(db, 'attendance/2026-11-16'), { ids: ['b1'] });
  });
});
const anon = () => env.unauthenticatedContext().firestore();
const as = (uid) => env.authenticatedContext(uid).firestore();
const anonAs = (uid) => env.authenticatedContext(uid, { firebase: { sign_in_provider: 'anonymous' } }).firestore();   // QR device (Firebase Anonymous auth)
const join = (db, uid, code, extra = {}) => {
  const b = writeBatch(db);
  b.set(doc(db, 'staffKeys/' + uid), { code });
  b.set(doc(db, 'staff/' + uid), { name: 'New', active: true, role: 'staff', joinedAt: serverTimestamp(), ...extra });
  return b.commit();
};
const best = (uid, extra = {}) => ({ name: 'BEST B', stage: 'first', cls: [false, false, false, false, false], stageHistory: [],
  firstVisit: '2026-11-16', createdAt: serverTimestamp(), createdBy: uid, updatedAt: serverTimestamp(), updatedBy: uid, ...extra });

test('unauthenticated: cannot read bests / logs / attendance / staff / config', async () => {
  await assertFails(getDoc(doc(anon(), 'bests/b1')));
  await assertFails(getDocs(collection(anon(), 'bests')));
  await assertFails(getDoc(doc(anon(), 'bests/b1/logs/l1')));
  await assertFails(getDoc(doc(anon(), 'attendance/2026-11-16')));
  await assertFails(getDocs(collection(anon(), 'staff')));
  await assertFails(getDoc(doc(anon(), 'config/invite')));
});
test('unauthenticated: cannot write', async () => {
  await assertFails(setDoc(doc(anon(), 'bests/x'), best('nobody')));
  await assertFails(join(anon(), 'nobody', CODE));
});
test('signed-in non-staff: cannot read or write BEST data', async () => {
  const db = as('stranger');
  await assertFails(getDoc(doc(db, 'bests/b1')));
  await assertFails(getDocs(collection(db, 'bests')));
  await assertFails(getDocs(collection(db, 'staff')));
  await assertFails(getDoc(doc(db, 'attendance/2026-11-16')));
  await assertFails(setDoc(doc(db, 'bests/x'), best('stranger')));
  await assertSucceeds(getDoc(doc(db, 'staff/stranger')));   // may look up own (missing) staff doc
});
test('deactivated staff: denied', async () => {
  const db = as('gone1');
  await assertFails(getDoc(doc(db, 'bests/b1')));
  await assertFails(setDoc(doc(db, 'bests/x'), best('gone1')));
  await assertFails(updateDoc(doc(db, 'staff/gone1'), { active: true }));
});
test('QR device (anonymous auth): no key -> no data; wrong key denied; right key auto-joins and can read/create/update', async () => {
  const db = anonAs('dev1');
  await assertFails(getDoc(doc(db, 'bests/b1')));
  await assertFails(getDocs(collection(db, 'bests')));
  await assertFails(setDoc(doc(db, 'staff/dev1'), { name: '동역자', active: true, role: 'staff', joinedAt: serverTimestamp() }));   // no key at all
  await assertFails(join(db, 'dev1', 'WRONGKEY2026ABCD'));
  await assertFails(join(db, 'dev1', 'TESTC0DE'));            // old-style / partial key
  await assertFails(join(db, 'dev1', CODE, { role: 'admin' }));
  await assertSucceeds(join(db, 'dev1', CODE));
  await assertSucceeds(getDocs(collection(db, 'bests')));
  await assertSucceeds(setDoc(doc(db, 'bests/d1'), best('dev1', { nick: 'Grace' })));
  await assertSucceeds(updateDoc(doc(db, 'bests/d1'), { stage: 'welcome', nick: 'Gracie', updatedAt: serverTimestamp(), updatedBy: 'dev1' }));
  await assertSucceeds(setDoc(doc(db, 'bests/b1/logs/l7'), { date: '2026-11-17', method: 'phone', by: 'dev1', at: serverTimestamp() }));
  await assertSucceeds(setDoc(doc(db, 'attendance/2026-11-16'), { ids: arrayUnion('d1'), updatedAt: serverTimestamp(), by: 'dev1' }, { merge: true }));
  await assertFails(getDoc(doc(db, 'config/invite')));       // key never readable
  await assertFails(deleteDoc(doc(db, 'bests/b1')));          // delete stays admin-only
});
test('QR device deactivated by admin loses access', async () => {
  await assertSucceeds(join(anonAs('dev2'), 'dev2', CODE));
  await assertSucceeds(updateDoc(doc(as('admin1'), 'staff/dev2'), { active: false }));
  await assertFails(getDoc(doc(anonAs('dev2'), 'bests/b1')));
  await assertFails(updateDoc(doc(anonAs('dev2'), 'staff/dev2'), { active: true }));
});
test('join: wrong invite code denied, right code allowed, cannot self-grant admin', async () => {
  await assertFails(join(as('u2'), 'u2', 'WRONG1234567890A'));
  await assertFails(join(as('u3'), 'u3', CODE, { role: 'admin' }));
  await assertFails(join(as('u4'), 'u5', CODE));   // someone else's uid
  await assertSucceeds(join(as('u2'), 'u2', CODE));
  await assertSucceeds(getDoc(doc(as('u2'), 'bests/b1')));
});
test('invite code is never readable, even by staff/admin; only admin can change it', async () => {
  await assertFails(getDoc(doc(as('staff1'), 'config/invite')));
  await assertFails(getDoc(doc(as('admin1'), 'config/invite')));
  await assertFails(getDoc(doc(as('staff1'), 'staffKeys/staff1')));
  await assertFails(setDoc(doc(as('staff1'), 'config/invite'), { code: 'ABCDEFGHJKLMNPQR', updatedAt: serverTimestamp() }));
  await assertFails(setDoc(doc(as('admin1'), 'config/invite'), { code: 'ABCDEFGH', updatedAt: serverTimestamp() }));   // too short for a church key
  await assertSucceeds(setDoc(doc(as('admin1'), 'config/invite'), { code: 'ABCDEFGHJKLMNPQR', updatedAt: serverTimestamp() }));
});
test('staff: read + register + update BEST, log contacts, attendance', async () => {
  const db = as('staff1');
  await assertSucceeds(getDoc(doc(db, 'bests/b1')));
  await assertSucceeds(getDocs(collection(db, 'staff')));
  await assertSucceeds(setDoc(doc(db, 'bests/b2'), best('staff1', { caretaker: 'admin1' })));
  await assertSucceeds(updateDoc(doc(db, 'bests/b2'), { stage: 'welcome', updatedAt: serverTimestamp(), updatedBy: 'staff1' }));
  await assertSucceeds(setDoc(doc(db, 'bests/b2/logs/l9'), { date: '2026-11-17', method: 'line', content: 'hi', by: 'staff1', at: serverTimestamp() }));
  await assertSucceeds(setDoc(doc(db, 'attendance/2026-11-16'), { ids: arrayUnion('b2'), updatedAt: serverTimestamp(), by: 'staff1' }, { merge: true }));
});
test('staff: validation — bad stage, extra field, oversized, forged author, bad date id', async () => {
  const db = as('staff1');
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { stage: 'vip' })));
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { hacked: true })));
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { name: 'x'.repeat(61) })));
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { nick: 'x'.repeat(21) })));
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { nick: 42 })));
  await assertSucceeds(setDoc(doc(db, 'bests/b4'), best('staff1', { nick: '小恩 Grace' })));
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { photo: 'x'.repeat(300001) })));
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { createdBy: 'admin1' })));
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { firstVisit: '17/11/2026' })));
  await assertFails(setDoc(doc(db, 'bests/b1/logs/l8'), { date: '2026-11-17', method: 'phone', by: 'admin1', at: serverTimestamp() }));
  await assertFails(setDoc(doc(db, 'attendance/sunday'), { ids: [], updatedAt: serverTimestamp(), by: 'staff1' }));
  await assertFails(deleteDoc(doc(db, 'bests/b1')));          // delete = admin only
});
test('phone / LINE removed: never on new cards; old values stay harmless (untouched or removed, never changed)', async () => {
  const db = as('staff1');
  await assertFails(setDoc(doc(db, 'bests/n1'), best('staff1', { phone: '0912' })));
  await assertFails(setDoc(doc(db, 'bests/n1'), best('staff1', { line: 'abc' })));
  await env.withSecurityRulesDisabled(async (ctx) => { await setDoc(doc(ctx.firestore(), 'bests/old1'), best('staff1', { phone: '0912-345-678', line: 'old_line' })); });
  await assertSucceeds(updateDoc(doc(db, 'bests/old1'), { stage: 'welcome', job: '老師', updatedAt: serverTimestamp(), updatedBy: 'staff1' }));   // old value untouched
  await assertFails(updateDoc(doc(db, 'bests/old1'), { phone: '0999', updatedAt: serverTimestamp(), updatedBy: 'staff1' }));
  await assertFails(updateDoc(doc(db, 'bests/old1'), { line: 'new', updatedAt: serverTimestamp(), updatedBy: 'staff1' }));
  const { deleteField } = await import('firebase/firestore');
  await assertSucceeds(updateDoc(doc(db, 'bests/old1'), { phone: deleteField(), line: deleteField(), updatedAt: serverTimestamp(), updatedBy: 'staff1' }));
});
test('occupation / school(dept) / grade: optional short text <= 40', async () => {
  const db = as('staff1');
  await assertSucceeds(setDoc(doc(db, 'bests/j1'), best('staff1', { job: '工程師', school: '台灣大學(資工系)', grade: '大三' })));
  await assertSucceeds(setDoc(doc(db, 'bests/j2'), best('staff1')));
  await assertFails(setDoc(doc(db, 'bests/j3'), best('staff1', { job: 'x'.repeat(41) })));
  await assertFails(setDoc(doc(db, 'bests/j3'), best('staff1', { school: 'x'.repeat(41) })));
  await assertFails(setDoc(doc(db, 'bests/j3'), best('staff1', { grade: 3 })));
});
test('supplements (notes): any staff appends; text 1-500; author/time forced; no edits; author or admin deletes', async () => {
  const note = (uid, extra = {}) => ({ text: '補充內容', by: uid, byName: 'Staff One', at: serverTimestamp(), ...extra });
  const db = as('staff1');
  await assertSucceeds(setDoc(doc(db, 'bests/b1/notes/n1'), note('staff1')));
  await assertFails(setDoc(doc(anonAs('dev9'), 'bests/b1/notes/x'), note('dev9')));       // device without the key: cannot add
  await assertFails(getDoc(doc(anonAs('dev9'), 'bests/b1/notes/n1')));                     // non-staff device cannot read
  await assertFails(getDoc(doc(anon(), 'bests/b1/notes/n1')));
  await assertFails(setDoc(doc(db, 'bests/b1/notes/n2'), note('staff1', { text: 'x'.repeat(501) })));
  await assertFails(setDoc(doc(db, 'bests/b1/notes/n2'), note('staff1', { text: '' })));
  await assertFails(setDoc(doc(db, 'bests/b1/notes/n2'), note('admin1')));                 // forged author
  await assertFails(setDoc(doc(db, 'bests/b1/notes/n2'), note('staff1', { extra: 1 })));
  await assertSucceeds(setDoc(doc(db, 'bests/b1/notes/n2'), note('staff1', { text: 'x'.repeat(500) })));
  await assertSucceeds(getDocs(collection(db, 'bests/b1/notes')));
  await assertFails(updateDoc(doc(db, 'bests/b1/notes/n1'), { text: 'edited' }));        // append-only
  await assertSucceeds(join(anonAs('dev3'), 'dev3', CODE));
  await assertSucceeds(setDoc(doc(anonAs('dev3'), 'bests/b1/notes/n3'), note('dev3', { byName: '동역자' })));
  await assertFails(deleteDoc(doc(anonAs('dev3'), 'bests/b1/notes/n1')));                // not own, not admin
  await assertSucceeds(deleteDoc(doc(anonAs('dev3'), 'bests/b1/notes/n3')));             // own
  await assertSucceeds(deleteDoc(doc(as('admin1'), 'bests/b1/notes/n1')));               // admin: any
});
test('staff cannot change own role/active; admin can deactivate others but not self', async () => {
  await assertFails(updateDoc(doc(as('staff1'), 'staff/staff1'), { role: 'admin' }));
  await assertFails(updateDoc(doc(as('staff1'), 'staff/staff1'), { active: false }));
  await assertSucceeds(updateDoc(doc(as('staff1'), 'staff/staff1'), { name: 'Renamed' }));
  await assertFails(updateDoc(doc(as('staff1'), 'staff/admin1'), { active: false }));
  await assertSucceeds(updateDoc(doc(as('admin1'), 'staff/staff1'), { active: false }));
  await assertFails(updateDoc(doc(as('admin1'), 'staff/admin1'), { active: false }));
  await assertFails(updateDoc(doc(as('admin1'), 'staff/gone1'), { role: 'admin' }));
  await assertSucceeds(deleteDoc(doc(as('admin1'), 'bests/b1')));
});
