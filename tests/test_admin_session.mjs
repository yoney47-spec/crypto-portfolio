import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

test('reload bridge stores only a grant, handles unavailable storage and cleans up expiry', async () => {
  const source = await readFile(new URL('../components/admin_session.js', import.meta.url), 'utf8');
  const {default: mount} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
  const stored = new Map(), events = [], listeners = new Map(), timers = new Map();
  let now = 0, counter = 0;
  globalThis.sessionStorage = {
    getItem: key => stored.get(key) ?? null,
    setItem: (key, value) => stored.set(key, value),
    removeItem: key => stored.delete(key),
  };
  globalThis.performance = {now: () => now};
  globalThis.document = globalThis.window = {
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: name => listeners.delete(name),
  };
  globalThis.setTimeout = (fn, ms) => { timers.set(++counter, {fn, ms}); return counter; };
  globalThis.clearTimeout = id => timers.delete(id);
  const run = data => mount({data, setTriggerValue: (name, value) => events.push({name, ...value})});
  run({id: 'first', action: 'read'});
  assert.equal(events.pop().handle, '');
  const handle = 'A'.repeat(43);
  const stop = run({id: 'login', action: 'write', handle, remaining_ms: 600000});
  assert.equal(events.pop().ok, true);
  assert.deepEqual([...stored.values()], [handle]);
  stop();
  run({id: 'reload', action: 'read'});
  assert.equal(events.pop().handle, handle);
  const stopAgain = run({id: 'resume', action: 'write', handle, remaining_ms: 1000});
  events.length = 0;
  now = 999; listeners.get('visibilitychange')(); assert.equal(events.length, 0);
  now = 1001; listeners.get('pageshow')();
  assert.equal(events.pop().kind, 'expired');
  assert.equal(stored.size, 0);
  listeners.get('pageshow')(); assert.equal(events.length, 0);
  stopAgain(); assert.equal(listeners.size, 0); assert.equal(timers.size, 0);
  const stopThird = run({id: 'next', action: 'write', handle, remaining_ms: 2000}); stopThird();
  run({id: 'logout', action: 'clear'}); assert.equal(stored.size, 0);
  run({id: 'after-logout', action: 'read'}); assert.equal(events.pop().handle, '');
  globalThis.sessionStorage = {getItem() { throw Error('blocked'); }, setItem() { throw Error('blocked'); }};
  const stopBlocked = run({id: 'blocked', action: 'write', handle, remaining_ms: 1000});
  assert.equal(events.pop().ok, false);
  stopBlocked();
});
