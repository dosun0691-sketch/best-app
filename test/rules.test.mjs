// Firestore security rules tests — run: cd best-app && firebase emulators:exec --only firestore "cd test && npm test"
import { test, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { initializeTestEnvironment, assertFails, assertSucceeds } from '@firebase/rules-unit-testing';
import { doc, getDoc, getDocs, setDoc, updateDoc, deleteDoc, collection, writeBatch, serverTimestamp, arrayUnion, setLogLevel } from 'firebase/firestore';
setLogLevel('silent');

let env;
const CODE = 'TESTC0DE';
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
test('join: wrong invite code denied, right code allowed, cannot self-grant admin', async () => {
  await assertFails(join(as('u2'), 'u2', 'WRONG123'));
  await assertFails(join(as('u3'), 'u3', CODE, { role: 'admin' }));
  await assertFails(join(as('u4'), 'u5', CODE));   // someone else's uid
  await assertSucceeds(join(as('u2'), 'u2', CODE));
  await assertSucceeds(getDoc(doc(as('u2'), 'bests/b1')));
});
test('invite code is never readable, even by staff/admin; only admin can change it', async () => {
  await assertFails(getDoc(doc(as('staff1'), 'config/invite')));
  await assertFails(getDoc(doc(as('admin1'), 'config/invite')));
  await assertFails(getDoc(doc(as('staff1'), 'staffKeys/staff1')));
  await assertFails(setDoc(doc(as('staff1'), 'config/invite'), { code: 'ABCDEFGH', updatedAt: serverTimestamp() }));
  await assertSucceeds(setDoc(doc(as('admin1'), 'config/invite'), { code: 'ABCDEFGH', updatedAt: serverTimestamp() }));
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
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { photo: 'x'.repeat(300001) })));
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { createdBy: 'admin1' })));
  await assertFails(setDoc(doc(db, 'bests/b3'), best('staff1', { firstVisit: '17/11/2026' })));
  await assertFails(setDoc(doc(db, 'bests/b1/logs/l8'), { date: '2026-11-17', method: 'phone', by: 'admin1', at: serverTimestamp() }));
  await assertFails(setDoc(doc(db, 'attendance/sunday'), { ids: [], updatedAt: serverTimestamp(), by: 'staff1' }));
  await assertFails(deleteDoc(doc(db, 'bests/b1')));          // delete = admin only
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
