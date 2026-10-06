"""9router integration: auto-login, token cache, device-code OAuth connect."""
from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
from html import unescape
from urllib.parse import urlencode

import requests as std_requests
from curl_cffi import requests as cffi_requests

from .config import (
    ROUTER_BASE, ROUTER_PASSWORD, ROUTER_AUTH_TOKEN, ROUTER_TOKEN_FILE,
)
from .colors import dim, err, info, ok, warn
from .utils import make_session, extract_uid, print_safe as _print

_token_lock = threading.Lock()
_cached_token: str | None = None


# =====================================================================
# JWT and token cache helpers
# =====================================================================
def _jwt_exp(token: str) -> float:
    try:
        raw = token.split("=", 1)[1] if "=" in token else token
        payload = raw.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return float(data.get("exp", 0))
    except Exception:
        return 0


def _token_is_fresh(token: str, margin: int = 120) -> bool:
    if not token:
        return False
    raw = token.split("=", 1)[1] if token.startswith("auth_token=") else token
    exp = _jwt_exp(raw)
    if exp == 0:
        return bool(raw)
    return exp > time.time() + margin


def _normalize_token(value: str) -> str:
    if not value:
        return ""
    if value.startswith("auth_token="):
        return value
    return f"auth_token={value}"


def _load_cached_token() -> str | None:
    try:
        if not os.path.exists(ROUTER_TOKEN_FILE):
            return None
        with open(ROUTER_TOKEN_FILE, encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("token") or ""
        if _token_is_fresh(token):
            return token
    except Exception:
        pass
    return None


def _save_cached_token(token: str) -> None:
    try:
        with open(ROUTER_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "token": token,
                "saved_at": int(time.time()),
                "exp": int(_jwt_exp(token.split("=", 1)[-1])),
            }, f)
    except Exception:
        pass


def _extract_token_from_response(resp) -> str | None:
    try:
        for cookie in resp.cookies:
            if cookie.name in ("auth_token", "token", "access_token"):
                return _normalize_token(cookie.value)
    except Exception:
        pass

    try:
        data = resp.json()
    except Exception:
        data = None

    if isinstance(data, dict):
        for key in ("auth_token", "authToken", "token", "access_token", "accessToken"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return _normalize_token(value)
        nested = data.get("data") or data.get("result") or {}
        if isinstance(nested, dict):
            for key in ("auth_token", "authToken", "token", "access_token"):
                value = nested.get(key)
                if isinstance(value, str) and value:
                    return _normalize_token(value)
    return None


# =====================================================================
# Auto-login (API and browser fallback)
# =====================================================================
def _login_via_api(router_base: str, password: str) -> str | None:
    session = cffi_requests.Session(impersonate="chrome136")
    session.headers.update({
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin":  router_base,
        "referer": f"{router_base}/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
    })
    try:
        session.get(f"{router_base}/", timeout=10, allow_redirects=True)
    except Exception:
        pass

    endpoints = [
        ("/api/auth/login",   {"password": password}),
        ("/api/auth",         {"password": password}),
        ("/api/login",        {"password": password}),
        ("/api/session",      {"password": password}),
        ("/auth/login",       {"password": password}),
        ("/login",            {"password": password}),
        ("/api/auth/login",   {"username": "admin", "password": password}),
        ("/api/login",        {"username": "admin", "password": password}),
    ]
    for path, body in endpoints:
        try:
            r = session.post(f"{router_base}{path}", json=body, timeout=15)
            if r.status_code in (200, 201, 204):
                token = _extract_token_from_response(r)
                if token:
                    _print(f"  {ok('[OK]')} 9router login via API ({path})")
                    return token
        except Exception:
            continue

    for path in ("/api/auth/login", "/api/login", "/login"):
        try:
            r = session.post(
                f"{router_base}{path}",
                data=f"password={password}",
                headers={**session.headers, "content-type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            if r.status_code in (200, 201, 204):
                token = _extract_token_from_response(r)
                if token:
                    _print(f"  {ok('[OK]')} 9router login via form ({path})")
                    return token
        except Exception:
            continue
    return None


def _login_via_browser(router_base: str, password: str) -> str | None:
    try:
        from camoufox.sync_api import Camoufox
    except Exception as e:
        _print(f"  {err('[ERR]')} Camoufox not available: {e}")
        return None

    _print(f"  {info('[*]')} Fallback: browser login to 9router...")
    try:
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            page.goto(f"{router_base}/", wait_until="domcontentloaded", timeout=25_000)
            time.sleep(2)

            password_selector = (
                'input[type="password"], input[name="password"], '
                'input[placeholder*="assword" i], '
                'input[placeholder*="sandi" i]'
            )
            try:
                page.wait_for_selector(password_selector, timeout=10_000)
            except Exception:
                _print(f"  {err('[ERR]')} no password input found on 9router UI")
                return None

            page.fill(password_selector, password)
            time.sleep(0.4)

            submitted = False
            for selector in (
                'button[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'button:has-text("Masuk")',
                'input[type="submit"]',
            ):
                try:
                    el = page.locator(selector).first
                    if el.count() > 0:
                        el.click(timeout=3_000)
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                page.press(password_selector, "Enter")

            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            time.sleep(2)

            for cookie in page.context.cookies():
                if cookie.get("name") in ("auth_token", "token", "access_token"):
                    token = _normalize_token(cookie["value"])
                    if token:
                        _print(f"  {ok('[OK]')} 9router login via browser")
                        return token

            try:
                storage = page.evaluate(
                    "() => JSON.stringify(Object.assign({}, window.localStorage))"
                )
                if storage:
                    for key in ("auth_token", "authToken", "token", "access_token"):
                        m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', storage)
                        if m:
                            token = _normalize_token(m.group(1))
                            if token:
                                _print(f"  {ok('[OK]')} 9router token from localStorage")
                                return token
            except Exception:
                pass
    except Exception as e:
        _print(f"  {err('[ERR]')} browser login error: {e}")
    return None


def get_router_token(
    router_base: str = ROUTER_BASE,
    password: str = ROUTER_PASSWORD,
    force: bool = False,
) -> str | None:
    """
    Retrieve an auth_token using the following priority:
      1. memory cache
      2. disk cache (.9router_token.json)
      3. ROUTER_AUTH_TOKEN from .env
      4. auto-login via API
      5. auto-login via Camoufox browser
    """
    global _cached_token

    with _token_lock:
        if not force and _cached_token and _token_is_fresh(_cached_token):
            return _cached_token

        if not force:
            disk_token = _load_cached_token()
            if disk_token:
                _cached_token = disk_token
                _print(f"  {info('[i]')} 9router token loaded from disk cache")
                return disk_token

        if not force and ROUTER_AUTH_TOKEN and _token_is_fresh(ROUTER_AUTH_TOKEN):
            _cached_token = ROUTER_AUTH_TOKEN
            _print(f"  {info('[i]')} 9router token loaded from env")
            return ROUTER_AUTH_TOKEN

        _print(f"  {info('[*]')} Auto-login 9router...")
        token = _login_via_api(router_base, password)
        if not token:
            token = _login_via_browser(router_base, password)

        if token:
            _cached_token = token
            _save_cached_token(token)
            return token

        if ROUTER_AUTH_TOKEN:
            _print(f"  {warn('[!]')} auto-login failed, using env token (may be expired)")
            _cached_token = ROUTER_AUTH_TOKEN
            return ROUTER_AUTH_TOKEN
        return None


# =====================================================================
# Approve variants and device-code flow
# =====================================================================
def _extract_hidden_fields(html: str) -> dict:
    """Extract all <input type="hidden" name="..." value="..."> from HTML."""
    out: dict = {}
    for match in re.finditer(r'<input[^>]*type=["\']hidden["\'][^>]*>', html or "", re.I):
        tag = match.group(0)
        name_match  = re.search(r'name=["\']([^"\']+)["\']', tag, re.I)
        value_match = re.search(r'value=["\']([^"\']*)["\']', tag, re.I)
        if name_match:
            out[name_match.group(1)] = unescape(value_match.group(1)) if value_match else ""
    return out


def _try_approve_variants(
    session,
    user_code: str,
    uid: str,
    hidden_fields: dict,
) -> tuple[bool, int, str]:
    """Try several approve endpoints and body variants until one succeeds."""
    endpoints = [
        "https://auth.x.ai/oauth2/device/approve",
        "https://accounts.x.ai/oauth2/device/approve",
        "https://accounts.x.ai/oauth2/device/consent",
    ]

    base: dict = {}
    for key, value in (hidden_fields or {}).items():
        if value is None:
            continue
        base[key] = str(value)
    base["user_code"] = user_code
    base.setdefault("principal_type", "User")
    base.setdefault("principal_id", uid)

    decisions = [
        {"action": "allow"},
        {"decision": "allow"},
        {"consent": "allow"},
        {"approve": "true"},
        {"allow": "true"},
        {"submit": "allow"},
        {"action": "approve"},
        {"decision": "approve"},
    ]

    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "origin": "https://accounts.x.ai",
        "referer": f"https://accounts.x.ai/oauth2/device/consent?user_code={user_code}",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
    }

    last_status = 0
    last_body   = ""
    for endpoint in endpoints:
        for decision in decisions:
            body = urlencode({**base, **decision})
            try:
                r = session.post(
                    endpoint,
                    data=body,
                    headers=headers,
                    timeout=20,
                    allow_redirects=True,
                )
                last_status = r.status_code
                last_body   = r.text[:200]
                if r.status_code in (200, 201, 204, 302, 303):
                    return True, r.status_code, last_body
            except Exception as e:
                last_body = str(e)
                continue
    return False, last_status, last_body


def connect_to_router(
    cookies: dict,
    router_base: str = ROUTER_BASE,
    router_token: str | None = None,
    proxy: str | None = None,
    poll_retries: int = 8,
    _retried: bool = False,
) -> bool:
    _print(f"  {info('[+]')} Connect 9router...")

    if not router_token:
        router_token = get_router_token(router_base)
    if not router_token:
        _print(f"  {err('[ERR]')} cannot obtain 9router auth_token")
        return False

    cookie_value = (
        router_token.split("=", 1)[1]
        if router_token.startswith("auth_token=") else router_token
    )
    _print(f"  {dim('[dbg]')} token len={len(cookie_value)}")

    uid = extract_uid(cookies)
    _print(f"  {dim('[dbg]')} uid={uid[:36]}")

    # ---- 1. device-code -----------------------------------------
    try:
        resp = std_requests.get(
            f"{router_base}/api/oauth/grok-cli/device-code",
            cookies={"auth_token": cookie_value},
            headers={"Accept": "*/*"},
            timeout=15,
        )
    except Exception as e:
        _print(f"  {err('[ERR]')} 9router unreachable: {e}")
        return False

    _print(f"  {dim('[dbg]')} device-code -> HTTP {resp.status_code}")

    if resp.status_code == 401 and not _retried:
        _print(f"  {warn('[!]')} 401 received, attempting token refresh...")
        new_token = get_router_token(router_base, force=True)
        if new_token and new_token != router_token:
            return connect_to_router(
                cookies=cookies, router_base=router_base,
                router_token=new_token, proxy=proxy,
                poll_retries=poll_retries, _retried=True,
            )
        _print(f"  {err('[ERR]')} token refresh failed or returned same token")
        return False

    if resp.status_code != 200:
        _print(f"  {err('[ERR]')} device-code HTTP {resp.status_code}: {resp.text[:160]}")
        return False

    try:
        data = resp.json()
    except Exception as e:
        _print(f"  {err('[ERR]')} parse device-code failed: {e} | body={resp.text[:160]}")
        return False

    _print(f"  {dim('[dbg]')} device-code fields: {list(data.keys())}")

    device_code   = data.get("device_code")  or data.get("deviceCode")
    code_verifier = data.get("codeVerifier") or data.get("code_verifier")
    user_code     = data.get("user_code")    or data.get("userCode")
    interval      = data.get("interval")     or 5

    if not device_code or not user_code:
        _print(f"  {err('[ERR]')} device_code/user_code missing: {data}")
        return False
    _print(f"  {dim('[dbg]')} user_code={user_code} interval={interval}")

    # ---- 2. consent page + hidden fields ------------------------
    session = make_session(proxy)
    session.cookies.update(cookies)
    session.headers.update({
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
    })

    consent_url = f"https://accounts.x.ai/oauth2/device/consent?user_code={user_code}"
    hidden_fields: dict = {}
    try:
        r0 = session.get(consent_url, timeout=20, allow_redirects=True)
        _print(f"  {dim('[dbg]')} consent page -> HTTP {r0.status_code} (len={len(r0.text)})")
        hidden_fields = _extract_hidden_fields(r0.text)
        if hidden_fields:
            _print(f"  {dim('[dbg]')} hidden fields: {list(hidden_fields.keys())}")
            for key in ("consent_token", "castle_request_token", "csrf_token", "_csrf"):
                if hidden_fields.get(key):
                    value = hidden_fields[key]
                    _print(f"  {dim('[dbg]')}   {key}={value[:24]}... (len={len(value)})")
    except Exception as e:
        _print(f"  {dim('[dbg]')} consent page error: {e}")

    # ---- 3. verify ----------------------------------------------
    verify_headers = {
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://accounts.x.ai",
        "referer": f"https://accounts.x.ai/oauth2/device?user_code={user_code}",
        "user-agent": session.headers["user-agent"],
    }
    try:
        v = session.post(
            "https://auth.x.ai/oauth2/device/verify",
            data=f"user_code={user_code}",
            headers=verify_headers,
            timeout=20,
            allow_redirects=True,
        )
        _print(f"  {dim('[dbg]')} verify -> HTTP {v.status_code}")
    except Exception as e:
        _print(f"  {err('[ERR]')} verify failed: {e}")
        return False

    # ---- 4. approve ---------------------------------------------
    approve_ok, status, body_text = _try_approve_variants(
        session, user_code, uid, hidden_fields,
    )
    if approve_ok:
        _print(f"  {dim('[dbg]')} approve -> HTTP {status}")
    else:
        _print(f"  {warn('[!]')} approve failed (HTTP {status}): {body_text[:120]}")
        _print(f"  {warn('[!]')} continuing to poll; approve may still unlock the device_code")

    # ---- 5. poll ------------------------------------------------
    _print(f"  {dim('[dbg]')} starting polling...")
    delay = max(float(interval), 5.0)
    last_pending_body: dict = {}

    for attempt in range(1, poll_retries + 1):
        try:
            poll = std_requests.post(
                f"{router_base}/api/oauth/grok-cli/poll",
                json={
                    "deviceCode": device_code,
                    "codeVerifier": code_verifier,
                    "extraData": None,
                },
                cookies={"auth_token": cookie_value},
                headers={"Accept": "*/*", "Content-Type": "application/json"},
                timeout=15,
            )
        except Exception as e:
            _print(f"  {dim('[dbg]')} poll #{attempt} exception: {e}")
            time.sleep(delay)
            continue

        if poll.status_code == 401 and not _retried:
            _print(f"  {warn('[!]')} poll 401, attempting token refresh...")
            new_token = get_router_token(router_base, force=True)
            if new_token and new_token != router_token:
                return connect_to_router(
                    cookies=cookies, router_base=router_base,
                    router_token=new_token, proxy=proxy,
                    poll_retries=poll_retries, _retried=True,
                )
            _print(f"  {err('[ERR]')} token refresh failed")
            return False

        if poll.status_code != 200:
            _print(f"  {dim('[dbg]')} poll #{attempt} HTTP {poll.status_code}: {poll.text[:160]}")
            if attempt < poll_retries:
                time.sleep(delay)
                continue
            _print(f"  {err('[ERR]')} poll HTTP {poll.status_code} after {poll_retries} tries")
            return False

        try:
            body_json = poll.json() if poll.text else {}
        except Exception:
            body_json = {}

        _print(f"  {dim('[dbg]')} poll #{attempt} -> {str(body_json)[:180]}")

        if body_json.get("success") is True:
            _print(f"  {ok('[OK]')} 9router connected")
            return True

        error_name = (body_json.get("error") or "").lower()
        last_pending_body = body_json

        if error_name == "slow_down":
            delay = min(delay + 3.0, 15.0)
            _print(f"  {dim('[dbg]')} slow_down, delay={delay}s")

        if body_json.get("pending") or error_name in ("authorization_pending", "slow_down"):
            if attempt < poll_retries:
                time.sleep(delay)
                continue
            _print(f"  {err('[ERR]')} poll still pending after {poll_retries} tries")
            _print(f"  {dim('[dbg]')} last poll body: {str(last_pending_body)[:200]}")
            return False

        error_msg = (
            body_json.get("errorDescription")
            or body_json.get("error")
            or body_json.get("message")
            or str(body_json)[:160]
        )
        if attempt < poll_retries:
            _print(f"  {dim('[dbg]')} poll #{attempt} error: {error_msg}")
            time.sleep(delay)
            continue
        _print(f"  {err('[ERR]')} poll error: {error_msg}")
        return False

    _print(f"  {err('[ERR]')} poll loop exhausted without result")
    return False