"""xAI signup flow driven by Camoufox headless browser."""
from __future__ import annotations

import datetime as _dt
import random
import threading
import time

from .config import FIRST_NAMES, LAST_NAMES
from .colors import bold, dim, err, ok, step, warn
from .router import connect_to_router
from .tempmail import get_provider
from .utils import extract_uid, parse_proxy, print_safe as _print

_write_lock = threading.Lock()


def register_one(
    password: str,
    proxy: str | None,
    router: bool,
    router_base: str,
    worker_id: int = 0,
) -> bool:
    prefix = f"{dim(f'[#{worker_id}]')}" if worker_id else ""

    # ---- create temp mail inbox (provider chosen by .env) -------
    ProviderClass = get_provider()
    mail = ProviderClass()
    if not mail.create_inbox():
        _print(f"{prefix} {err('[ERR]')} failed to create temp mail inbox")
        return False

    email  = mail.email
    given  = random.choice(FIRST_NAMES)
    family = random.choice(LAST_NAMES)
    _print(f"\n{prefix} {step('>>')} {bold(email)} - {given} {family}")

    from camoufox.sync_api import Camoufox

    launch: dict = {"headless": True}
    if proxy:
        launch["proxy"] = parse_proxy(proxy)
        launch["geoip"] = True

    uid = "-"
    cookies: dict = {}

    try:
        with Camoufox(**launch) as browser:
            page = browser.new_page()

            # 1) signup page
            _print(f"{prefix}  {step('[1/5]')} {warn('signup...')}")
            page.goto(
                "https://accounts.x.ai/sign-up",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            time.sleep(1.5)

            try:
                btn = page.locator("#onetrust-accept-btn-handler")
                if btn.count() > 0:
                    btn.click(timeout=2_000, force=True)
                    time.sleep(0.3)
            except Exception:
                pass

            page.click("text=Sign up with email", timeout=10_000)
            time.sleep(1)

            # 2) email
            page.fill('input[type="email"]', email)
            time.sleep(0.3)
            page.click('button[type="submit"]', timeout=8_000)
            time.sleep(2)
            _print(f"{prefix}  {step('[2/5]')} {ok('email sent')}")

            # 3) OTP
            signup_started_at = time.time()
            code = mail.wait_code(retries=20, delay=3, since_ts=signup_started_at)
            if not code:
                _print(f"{prefix}  {err('[ERR]')} OTP timeout")
                return False
            _print(f"{prefix}  {step('[3/5]')} {ok('OTP')} {bold(code)}")

            otp_input = page.locator('input[name="code"]')
            if otp_input.count() == 0:
                _print(f"{prefix}  {err('[ERR]')} no OTP input on page")
                return False
            otp_input.fill(code)
            time.sleep(0.3)
            page.click('button[type="submit"]', timeout=5_000)

            try:
                page.wait_for_selector(
                    'input[type="password"], [role="alert"], .error, '
                    'input[name="firstName"]',
                    timeout=15_000,
                )
            except Exception:
                pass
            time.sleep(1)

            # 4) password
            password_input = page.locator('input[type="password"]')
            if password_input.count() == 0:
                _print(f"{prefix}  {err('[ERR]')} password form did not appear")
                try:
                    page.screenshot(path=f"fail_{mail.username}.png", full_page=True)
                except Exception:
                    pass
                return False

            password_input.first.fill(password)
            time.sleep(0.2)
            if password_input.count() > 1:
                password_input.nth(1).fill(password)
            page.click('button[type="submit"]', timeout=5_000)
            time.sleep(2.5)

            # 5) name
            first_input = page.locator('input[name="firstName"], input[autocomplete="given-name"]')
            last_input  = page.locator('input[name="lastName"], input[autocomplete="family-name"]')
            if first_input.count() > 0:
                first_input.fill(given)
                last_input.fill(family)
                time.sleep(0.2)
                page.click('button[type="submit"]', timeout=5_000)
                try:
                    page.wait_for_url("**/console.x.ai/**", timeout=15_000)
                except Exception:
                    pass
                time.sleep(2)

            # 6) wait for SSO; retry login if it is missing
            def _all_cookies() -> dict:
                return {c["name"]: c["value"] for c in page.context.cookies()}

            def _has_sso(cookie_dict: dict) -> bool:
                return "sso" in cookie_dict or "sso-rw" in cookie_dict

            cookies = _all_cookies()
            for i in range(1, 7):
                if _has_sso(cookies):
                    break
                try:
                    if i in (1, 3, 5):
                        page.goto(
                            "https://console.x.ai/home",
                            wait_until="networkidle",
                            timeout=25_000,
                        )
                    else:
                        page.goto(
                            "https://accounts.x.ai/account",
                            wait_until="networkidle",
                            timeout=25_000,
                        )
                except Exception:
                    pass
                time.sleep(2)
                cookies = _all_cookies()

            if not _has_sso(cookies):
                _print(f"{prefix}  {warn('[~]')} signup finished without sso, retrying login...")
                try:
                    page.goto(
                        "https://accounts.x.ai/sign-in",
                        wait_until="domcontentloaded",
                        timeout=25_000,
                    )
                    time.sleep(1.5)

                    email_input = page.locator('input[type="email"]')
                    if email_input.count() > 0:
                        email_input.first.fill(email)
                        time.sleep(0.3)
                        page.click('button[type="submit"]', timeout=5_000)
                        time.sleep(2)

                    try:
                        page.wait_for_selector('input[type="password"]', timeout=8_000)
                    except Exception:
                        for selector in (
                            'text=Sign in with password',
                            'text=Use password',
                            'button:has-text("password")',
                        ):
                            try:
                                el = page.locator(selector).first
                                if el.count() > 0:
                                    el.click(timeout=3_000)
                                    time.sleep(1.5)
                                    break
                            except Exception:
                                continue

                    pw = page.locator('input[type="password"]')
                    if pw.count() > 0:
                        pw.first.fill(password)
                        time.sleep(0.3)
                        page.click('button[type="submit"]', timeout=5_000)
                        try:
                            page.wait_for_url("**/console.x.ai/**", timeout=15_000)
                        except Exception:
                            pass
                        time.sleep(2)

                    cookies = _all_cookies()
                    for _ in range(4):
                        if _has_sso(cookies):
                            break
                        try:
                            page.goto(
                                "https://console.x.ai/home",
                                wait_until="networkidle",
                                timeout=20_000,
                            )
                        except Exception:
                            pass
                        time.sleep(2)
                        cookies = _all_cookies()
                except Exception as e:
                    _print(f"{prefix}  {warn('[!]')} relogin error: {str(e)[:80]}")

            if not _has_sso(cookies):
                _print(f"{prefix}  {warn('[!]')} sso still missing")
                try:
                    page.screenshot(path=f"fail_{mail.username}.png", full_page=True)
                except Exception:
                    pass
            else:
                _print(f"{prefix}  {ok('[OK]')} account OK")

            uid = extract_uid(cookies)
            _print(f"{prefix}  {step('[4/5]')} uid={dim(str(uid)[:36])}")

    except Exception as e:
        _print(f"{prefix}  {err('[ERR]')} browser error: {e}")
        return False

    # ---- connect to 9router -------------------------------------
    router_status = "-"
    if uid == "-":
        _print(f"{prefix}  {warn('[!]')} empty uid, skipping 9router")
        router_status = "skipped_no_sso"
    elif router and cookies:
        connected = connect_to_router(
            cookies=cookies,
            router_base=router_base,
            proxy=proxy,
            poll_retries=8,
        )
        router_status = "connected" if connected else "failed"

    # ---- persist ------------------------------------------------
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{email}|{password}|{given} {family}|{uid}|router={router_status}|{ts}\n"
    with _write_lock:
        with open("accounts.txt", "a", encoding="utf-8") as f:
            f.write(line)
    _print(f"{prefix}  {step('[5/5]')} {ok('saved')} -> accounts.txt")
    return True