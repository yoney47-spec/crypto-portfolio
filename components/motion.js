// Progressive enhancements for CryptoFolio's own rendered UI. No requests,
// storage, framework internals, or replacement of Streamlit widget handlers.
const values = new Map();
const pages = new Map();

export default function () {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const mobile = matchMedia('(max-width: 768px)');
  const groups = new WeakMap();
  let frame = 0;
  let stopped = false;
  const animated = new Set();
  const animate = (element, frames, options) => {
    if (reduced.matches || !element.animate) return;
    const animation = element.animate(frames, options);
    animated.add(animation);
    animation.finished.catch(() => {}).finally(() => animated.delete(animation));
  };
  const schedule = () => {
    if (!frame && !stopped) frame = requestAnimationFrame(scan);
  };
  const resize = new ResizeObserver(schedule);

  function setPage(deck, index) {
    const buttons = [...deck.querySelectorAll('[data-insight-index]')];
    const cards = [...deck.querySelectorAll('[data-insight-card]')];
    index = Math.max(0, Math.min(index, cards.length - 1));
    pages.set(deck.dataset.insightId, index);
    deck.classList.add('cf-deck-enhanced');
    buttons.forEach((button, i) => {
      button.setAttribute('aria-selected', String(i === index));
      button.tabIndex = i === index ? 0 : -1;
    });
    cards.forEach((card, i) => {
      card.classList.toggle('cf-insight-active', i === index);
      if (mobile.matches) card.setAttribute('aria-hidden', String(i !== index));
      else card.removeAttribute('aria-hidden');
    });
  }

  function scan() {
    frame = 0;
    if (stopped) return;
    document.querySelectorAll('[data-motion-key]').forEach(element => {
      const key = element.dataset.motionKey;
      const value = element.getAttribute('aria-label');
      if (element.dataset.motionEnabled !== 'true') {
        values.delete(key);
        element.querySelectorAll('.cf-digit').forEach(d => d.getAnimations?.().forEach(a => a.cancel()));
        return;
      }
      if (values.get(key) === value) return;
      values.set(key, value);
      element.querySelectorAll('.cf-digit').forEach((digit, i) => {
        animate(digit, [{opacity: 0, transform: 'translateY(4px)', filter: 'blur(1px)'}, {opacity: 1, transform: 'translateY(0)', filter: 'blur(0)'}],
          {duration: 280, delay: Math.min(i * 16, 96), easing: 'cubic-bezier(0.22,1,0.36,1)', fill: 'backwards'});
      });
    });

    document.querySelectorAll('.st-key-currency_widget [data-baseweb="button-group"], .st-key-portfolio_period [data-baseweb="button-group"], [class*="st-key-asset_period_"] [data-baseweb="button-group"]').forEach(group => {
      const active = group.querySelector('button[kind="segmented_controlActive"]');
      if (!active) return;
      const box = group.getBoundingClientRect();
      const button = active.getBoundingClientRect();
      if (!box.width || !button.width) return;
      if (!groups.has(group)) { resize.observe(group); groups.set(group, true); }
      group.style.setProperty('--cf-tab-left', `${button.left - box.left}px`);
      group.style.setProperty('--cf-tab-width', `${button.width}px`);
      group.style.setProperty('--cf-tab-height', `${button.height}px`);
      group.classList.add('cf-sliding-tabs');
    });
    document.querySelectorAll('[data-insight-id]').forEach(deck => setPage(deck, pages.get(deck.dataset.insightId) || 0));
    // Only retain values for elements still on this page (including mask/logout).
    const present = new Set([...document.querySelectorAll('[data-motion-key]')].map(el => el.dataset.motionKey));
    for (const key of values.keys()) if (!present.has(key)) values.delete(key);
  }

  const click = event => {
    const button = event.target.closest?.('[data-insight-index]');
    const deck = button?.closest('[data-insight-id]');
    if (deck) setPage(deck, Number(button.dataset.insightIndex));
  };
  const keydown = event => {
    const button = event.target.closest?.('[data-insight-index]');
    const deck = button?.closest('[data-insight-id]');
    if (!deck || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const buttons = [...deck.querySelectorAll('[data-insight-index]')];
    const current = Number(button.dataset.insightIndex);
    const index = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
    event.preventDefault();
    setPage(deck, index); buttons[index].focus();
  };
  const stopAnimations = () => { if (reduced.matches) animated.forEach(a => a.cancel()); schedule(); };
  const observer = new MutationObserver(schedule);
  observer.observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true,
    attributeFilter: ['kind', 'data-motion-enabled', 'aria-label']});
  document.addEventListener('click', click);
  document.addEventListener('keydown', keydown);
  mobile.addEventListener('change', schedule);
  reduced.addEventListener('change', stopAnimations);
  schedule();
  return () => {
    stopped = true; observer.disconnect(); resize.disconnect(); cancelAnimationFrame(frame);
    animated.forEach(a => a.cancel());
    document.removeEventListener('click', click); document.removeEventListener('keydown', keydown);
    mobile.removeEventListener('change', schedule); reduced.removeEventListener('change', stopAnimations);
  };
}
