// Only an opaque ten-minute grant is stored. No password, Supabase JWT,
// refresh token, or portfolio data belongs in browser storage or URLs.
const storageKey = 'cryptofolio.admin.resume.v1';
let lastCommand = null;

export default function ({data, setTriggerValue}) {
  const send = (kind, values = {}) => setTriggerValue('event', {id: data.id, kind, ...values});
  const remove = () => { try { sessionStorage.removeItem(storageKey); } catch {} };
  if (data.id !== lastCommand) {
    lastCommand = data.id;
    if (data.action === 'read') {
      let handle = '';
      try { handle = sessionStorage.getItem(storageKey) || ''; } catch {}
      send('loaded', {handle: /^[A-Za-z0-9_-]{43}$/.test(handle) ? handle : ''});
    } else if (data.action === 'write') {
      let ok = false;
      try {
        sessionStorage.setItem(storageKey, data.handle);
        ok = sessionStorage.getItem(storageKey) === data.handle;
      } catch {}
      send('storage', {ok});
    } else if (data.action === 'clear') {
      remove();
    }
  }
  if (data.action !== 'write') return;
  // This is UI cleanup only. The server independently enforces the deadline
  // for every action even if a tab sleeps, JavaScript stops, or clocks differ.
  const remaining = Math.max(0, Math.min(600000, Number(data.remaining_ms) || 0));
  const deadline = performance.now() + remaining;
  let sent = false;
  const expire = () => {
    if (sent || performance.now() < deadline) return;
    sent = true;
    remove();
    send('expired');
  };
  const timer = setTimeout(expire, remaining + 100);
  document.addEventListener('visibilitychange', expire);
  window.addEventListener('pageshow', expire);
  return () => {
    clearTimeout(timer);
    document.removeEventListener('visibilitychange', expire);
    window.removeEventListener('pageshow', expire);
  };
}
