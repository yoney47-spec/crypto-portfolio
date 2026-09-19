"""Short-lived, revocable login grants. Supabase tokens never enter the browser."""
from copy import deepcopy
from hashlib import sha256
import re
import secrets
from threading import RLock
import time

LOGIN_LIFETIME_SECONDS = 600


class AdminSessionStore:
    def __init__(self, clock=None):
        self._clock = clock or time.time
        self._sessions = {}
        self._lock = RLock()

    @staticmethod
    def _key(handle):
        if not isinstance(handle, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', handle):
            return None
        return sha256(handle.encode('ascii')).hexdigest()

    def _prune(self):
        now = self._clock()
        for key, session in list(self._sessions.items()):
            if session['login_expires_at'] <= now:
                del self._sessions[key]

    def issue(self, session):
        with self._lock:
            self._prune()
            handle = secrets.token_urlsafe(32)
            saved = deepcopy(session)
            saved['login_expires_at'] = self._clock() + LOGIN_LIFETIME_SECONDS
            self._sessions[self._key(handle)] = saved
            return handle, deepcopy(saved)

    def get(self, handle):
        with self._lock:
            self._prune()
            return deepcopy(self._sessions.get(self._key(handle)))

    def update(self, handle, session):
        with self._lock:
            self._prune()
            key = self._key(handle)
            current = self._sessions.get(key)
            if not current or current['user_id'] != session['user_id']:
                return None
            saved = deepcopy(session)
            # Neither token refresh nor browser reload extends this deadline.
            saved['login_expires_at'] = current['login_expires_at']
            self._sessions[key] = saved
            return deepcopy(saved)

    def revoke(self, handle):
        with self._lock:
            return self._sessions.pop(self._key(handle), None)
