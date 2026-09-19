// Exercise lifecycle and privacy behavior without a browser or extra packages.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

test('motion only animates changed visible values and cleans up observers', async () => {
  let queued, animations = 0, cancels = 0, disconnects = 0;
  const listeners = new Map();
  const media = new Map();
  globalThis.matchMedia = query => {
    if (!media.has(query)) media.set(query, {matches: false, addEventListener() {}, removeEventListener() {}});
    return media.get(query);
  };
  globalThis.requestAnimationFrame = callback => { queued = callback; return 1; };
  globalThis.cancelAnimationFrame = () => {};
  let mutation;
  globalThis.MutationObserver = class {
    constructor(callback) { mutation = callback; }
    observe() {}
    disconnect() { disconnects++; }
  };
  globalThis.ResizeObserver = class { observe() {} disconnect() { disconnects++; } };
  const digit = {animate() { animations++; return {finished: new Promise(() => {}), cancel() { cancels++; }}; }, getAnimations() { return []; }};
  let label = '¥100';
  const value = {dataset: {motionKey: 'total', motionEnabled: 'true'}, getAttribute() { return label; }, querySelectorAll() { return [digit]; }};
  const classes = () => ({add() {}, toggle() {}});
  const buttons = [0,1,2].map(i => ({dataset: {insightIndex: String(i)}, attrs: {}, setAttribute(k,v) { this.attrs[k]=v; }, focus() { this.focused=true; }}));
  const cards = [0,1,2].map(() => ({attrs: {}, classList: classes(), setAttribute(k,v) { this.attrs[k]=v; }, removeAttribute(k) { delete this.attrs[k]; }}));
  const deck = {dataset: {insightId: 'today'}, classList: classes(), querySelectorAll(selector) { return selector.includes('index') ? buttons : cards; }};
  for (const button of buttons) button.closest = selector => selector.includes('index') ? button : deck;
  globalThis.document = {
    body: {}, querySelectorAll(selector) {
      if (selector === '[data-motion-key]') return [value];
      if (selector === '[data-insight-id]') return [deck];
      return [];
    },
    addEventListener(name, handler) { listeners.set(name,handler); },
    removeEventListener(name) { listeners.delete(name); }
  };
  const source = await readFile(new URL('../components/motion.js', import.meta.url), 'utf8');
  const {default: mount} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
  const flush = () => { const next=queued; queued=null; next?.(); };
  const cleanup = mount(); flush();
  assert.equal(animations, 1);
  mutation(); flush(); assert.equal(animations, 1, 'unchanged rerender must stay still');
  label = '$1.20'; mutation(); flush(); assert.equal(animations, 2);
  value.dataset.motionEnabled = 'false'; label = '••••••'; mutation(); flush();
  assert.equal(animations, 2, 'masked numbers must not animate');
  value.dataset.motionEnabled = 'true'; label = '¥200';
  media.get('(prefers-reduced-motion: reduce)').matches = true;
  mutation(); flush(); assert.equal(animations, 2);

  media.get('(max-width: 768px)').matches = true;
  mutation(); flush();
  assert.equal(cards[0].attrs['aria-hidden'], 'false');
  assert.equal(cards[1].attrs['aria-hidden'], 'true');
  listeners.get('click')({target: buttons[1]});
  assert.equal(buttons[1].attrs['aria-selected'], 'true');
  assert.equal(cards[1].attrs['aria-hidden'], 'false');
  listeners.get('keydown')({target: buttons[1], key:'End', preventDefault() {}});
  assert.equal(buttons[2].tabIndex, 0);
  assert.equal(buttons[2].focused, true);
  media.get('(max-width: 768px)').matches = false;
  mutation(); flush();
  assert.ok(cards.every(card => !('aria-hidden' in card.attrs)), 'desktop shows all sections');
  cleanup();
  assert.equal(listeners.size, 0);
  assert.equal(disconnects, 2);
  assert.equal(cancels, 2);
});
