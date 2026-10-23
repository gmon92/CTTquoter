"""Optional team sign-in. No authentication settings are enabled by default."""
from __future__ import annotations

import hmac
import os
import secrets
import threading
import time
from http.cookies import SimpleCookie, CookieError
from urllib.parse import urlsplit

COOKIE_NAME = "ctt_session"
SESSION_SECONDS = 8 * 60 * 60


class EmployeeAccess:
    def __init__(self, password="", public_origin=""):
        self.password = password
        self.origin = public_origin.rstrip("/")
        if password and len(password) < 16:
            raise ValueError("QUOTER_ACCESS_PASSWORD must contain at least 16 characters")
        if self.origin:
            parsed = urlsplit(self.origin)
            if (parsed.scheme != "https" or not parsed.netloc or parsed.path
                    or parsed.query or parsed.fragment or parsed.username or parsed.password):
                raise ValueError("QUOTER_PUBLIC_ORIGIN must be an HTTPS origin, such as https://quotes.example.com")
        self.sessions = {}
        self.attempts = {}
        self.lock = threading.Lock()

    @classmethod
    def from_environment(cls, host):
        password = os.environ.get("QUOTER_ACCESS_PASSWORD", "")
        origin = os.environ.get("QUOTER_PUBLIC_ORIGIN", "")
        if password and host not in ("127.0.0.1", "localhost", "::1") and not origin:
            raise ValueError("Set QUOTER_PUBLIC_ORIGIN to the HTTPS address before enabling public employee sign-in")
        return cls(password, origin)

    @property
    def enabled(self):
        return bool(self.password)

    def authorized(self, cookie):
        if not self.enabled:
            return True
        try:
            cookies = SimpleCookie()
            cookies.load(cookie or "")
            token = cookies[COOKIE_NAME].value if COOKIE_NAME in cookies else ""
        except CookieError:
            return False
        with self.lock:
            return self.sessions.get(token, 0) > time.time()

    def login(self, password, client):
        """Return (token, limited); throttle failed logins without storing passwords."""
        now = time.time()
        with self.lock:
            self.attempts = {key: value for key, value in self.attempts.items() if value[1] > now}
            failures, _ = self.attempts.get(client, (0, now + 60))
            if failures >= 5:
                return None, True
            if not hmac.compare_digest(password.encode(), self.password.encode()):
                if len(self.attempts) >= 1024:
                    self.attempts.pop(next(iter(self.attempts)))
                self.attempts[client] = (failures + 1, self.attempts.get(client, (0, now + 60))[1])
                return None, False
            self.attempts.pop(client, None)
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            if len(self.sessions) >= 256:
                self.sessions.pop(next(iter(self.sessions)))
            token = secrets.token_urlsafe(32)
            self.sessions[token] = now + SESSION_SECONDS
            return token, False

    def cookie(self, token, clear=False):
        secure = "; Secure" if self.origin else ""
        age = 0 if clear else SESSION_SECONDS
        return f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}{secure}"

    def logout(self, cookie):
        cookies = SimpleCookie()
        try:
            cookies.load(cookie or "")
            if COOKIE_NAME in cookies:
                with self.lock:
                    self.sessions.pop(cookies[COOKIE_NAME].value, None)
        except CookieError:
            pass


OPEN_ACCESS = EmployeeAccess()
