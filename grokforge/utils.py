"""Shared helpers: safe print, random email, session, JWT uid extraction."""
from __future__ import annotations

import base64
import json
import random
import string
import threading
from urllib.parse import urlparse

from curl_cffi import requests as cffi_requests

from .colors import C, bold, dim, err, info, ok, step, warn

_print_lock = threading.Lock()


def print_safe(*args, **kwargs):
    """Thread-safe print."""
    with _print_lock:
        print(*args, **kwargs)


__all__ = [
    "C", "bold", "dim", "err", "info", "ok", "step", "warn",
    "print_safe", "random_username", "make_session",
    "extract_uid", "parse_proxy",
]


def random_username(length: int = 12) -> str:
    """Generate a random alphanumeric username (default 12 chars)."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


def make_session(proxy: str | None = None) -> cffi_requests.Session:
    """Create a curl_cffi session impersonating Chrome 136."""
    s = cffi_requests.Session(impersonate="chrome136")
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    return s


def parse_proxy(proxy: str) -> dict:
    """Convert 'http://user:pass@host:port' into a Camoufox proxy config."""
    p = urlparse(proxy)
    cfg: dict = {"server": f"{p.scheme}://{p.hostname}:{p.port}"}
    if p.username:
        cfg["username"] = p.username
    if p.password:
        cfg["password"] = p.password
    return cfg


def extract_uid(cookies: dict) -> str:
    """Extract user id from the sso / sso-rw cookie (JWT sub claim)."""
    for key in ("sso", "sso-rw"):
        val = cookies.get(key)
        if not val:
            continue
        try:
            parts = val.split(".")
            if len(parts) < 2:
                continue
            payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
            data = json.loads(base64.b64decode(payload).decode())
            return (
                data.get("sub")
                or data.get("user_id")
                or data.get("session_id")
                or "-"
            )
        except Exception:
            continue
    return "-"