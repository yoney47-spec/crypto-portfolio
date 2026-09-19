"""Schedule data reads around the shared price cache, independent of UI ticks."""
import time


def refresh_dashboard(state, currency, view_id, fetch, *, clock=time.time, price_ttl=600):
    now = clock()
    previous = state.get(currency)
    if previous and previous['view_id'] == view_id and now < previous['next_check']:
        return previous
    result = fetch(currency)
    checked = clock()
    failed = bool(result.get('error'))
    data = previous['data'] if failed and previous and not previous['data'].get('error') else result
    next_check = checked + price_ttl
    stamp = data.get('updated_at')
    if not failed and not data.get('stale') and stamp is not None:
        # A 600-second timer can fire just before a 600-second price cache
        # expires and accidentally wait 20 minutes. Check after actual expiry.
        age = checked - stamp.timestamp()
        if 0 <= age <= price_ttl:
            next_check = max(checked + 60, stamp.timestamp() + price_ttl + 1)
    entry = dict(data=data, failed=failed, checked=checked, next_check=next_check, view_id=view_id)
    state[currency] = entry
    return entry
