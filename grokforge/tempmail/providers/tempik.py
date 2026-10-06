"""Tempik provider (tempik.neroism.web.id)."""
from __future__ import annotations

import re
import time

from curl_cffi import requests as cffi_requests

from ...config import (
    TEMPIK_BASE, TEMPIK_DEBUG, TEMPIK_DOMAINS, OTP_FALSE,
)
from ...utils import random_username, warn
from ..base import BaseTempMail
from ..registry import register


@register("tempik")
class TempikEmail(BaseTempMail):
    """
    Tempik temp mail provider.

    OTP extraction priority:
      1. data-otp="XXX-XXX" attribute
      2. subject line "... code: XXX-XXX"
      3. otp-banner-code">XXX-XXX<
      4. generic \\bXXX-XXX\\b fallback (must contain a digit)
    """

    DEFAULT_DOMAINS = TEMPIK_DOMAINS

    def __init__(self, email: str | None = None):
        if email is None:
            email = f"{random_username()}@{TEMPIK_DOMAINS[0]}"
        super().__init__(email)

        self.base = TEMPIK_BASE.rstrip("/")
        self.session = cffi_requests.Session(impersonate="chrome136")
        self.headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "referer": f"{self.base}/",
            "origin":  self.base,
        }
        self._created = False
        self._debug   = TEMPIK_DEBUG

    # -----------------------------------------------------------------
    # Inbox creation
    # -----------------------------------------------------------------
    def _bootstrap(self) -> None:
        try:
            self.session.get(f"{self.base}/", headers=self.headers, timeout=15)
        except Exception:
            pass

    def create_inbox(self) -> bool:
        if self._created:
            return True
        self._bootstrap()

        for endpoint, body in (
            ("/api/inboxes", {"address": self.email}),
            ("/api/inbox",   {"address": self.email}),
            ("/api/address", {"address": self.email}),
            ("/api/session", {"address": self.email}),
        ):
            try:
                r = self.session.post(
                    f"{self.base}{endpoint}",
                    json=body,
                    headers={**self.headers, "accept": "application/json"},
                    timeout=15,
                )
                if r.status_code in (200, 201, 204):
                    self._created = True
                    return True
            except Exception:
                continue

        if self.session.cookies:
            self._created = True
            return True

        try:
            r = self.session.get(f"{self.base}/", headers=self.headers, timeout=15)
            if r.status_code == 200:
                self._created = True
                return True
        except Exception:
            pass
        return False

    # -----------------------------------------------------------------
    # Fetch helpers
    # -----------------------------------------------------------------
    def _fetch_inbox_html(self) -> str:
        candidates = [
            f"{self.base}/",
            f"{self.base}/?address={self.email}",
            f"{self.base}/?email={self.email}",
            f"{self.base}/?inbox={self.email}",
            f"{self.base}/inbox/{self.email}",
        ]
        best = ""
        for url in candidates:
            try:
                r = self.session.get(url, headers=self.headers, timeout=15)
                if r.status_code != 200:
                    continue
                text = r.text
                if self.email in text:
                    return text
                if not best:
                    best = text
            except Exception:
                continue
        return best

    def _fetch_messages_json(self) -> list[dict]:
        for endpoint in (
            f"/api/messages?address={self.email}",
            f"/api/messages?inbox={self.email}",
            f"/api/inboxes/{self.email}/messages",
            f"/api/messages/{self.email}",
        ):
            try:
                r = self.session.get(
                    f"{self.base}{endpoint}",
                    headers={**self.headers, "accept": "application/json"},
                    timeout=15,
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                if isinstance(data, list):
                    return [m for m in data if isinstance(m, dict)]
                if isinstance(data, dict):
                    msgs = data.get("messages") or data.get("data") or data.get("emails")
                    if isinstance(msgs, list):
                        return [m for m in msgs if isinstance(m, dict)]
            except Exception:
                continue
        return []

    # -----------------------------------------------------------------
    # OTP extraction
    # -----------------------------------------------------------------
    @staticmethod
    def _normalize(code: str) -> str:
        return code.strip().upper().replace("-", "").replace(" ", "")

    @classmethod
    def _is_valid_otp(cls, code: str) -> bool:
        c = cls._normalize(code)
        if len(c) != 6 or not c.isalnum():
            return False
        if c in OTP_FALSE:
            return False
        if c.isalpha():
            return False
        if c.isdigit() and (c.startswith(("19", "20")) or len(set(c)) <= 2):
            return False
        if len(set(c)) <= 2:
            return False
        return True

    def _extract_from_text(self, text: str) -> str | None:
        if not text:
            return None

        m = re.search(r'data-otp="([A-Z0-9]{3}-[A-Z0-9]{3})"', text)
        if m:
            return m.group(1).replace("-", "")

        for pattern in (
            r"(?:SpaceXAI|SpaceX)\s+(?:sign[-\s]?in|confirmation|verification)\s+code[:\s]+([A-Z0-9]{3}-[A-Z0-9]{3})",
            r"(?:sign[-\s]?in|confirmation|verification)\s+code[:\s]+([A-Z0-9]{3}-[A-Z0-9]{3})",
        ):
            m = re.search(pattern, text, re.I)
            if m:
                return m.group(1).replace("-", "")

        m = re.search(r'otp-banner-code"[^>]*>([A-Z0-9]{3}-[A-Z0-9]{3})<', text)
        if m:
            return m.group(1).replace("-", "")

        for m in re.findall(r"\b([A-Z0-9]{3}-[A-Z0-9]{3})\b", text):
            if any(ch.isdigit() for ch in m):
                return m.replace("-", "")
        return None

    def _extract_from_payload(self, payload) -> str | None:
        if isinstance(payload, str):
            return self._extract_from_text(payload)
        if not isinstance(payload, dict):
            return None
        parts: list[str] = []
        for field in ("subject", "body", "html", "text", "content",
                      "snippet", "raw", "message"):
            value = payload.get(field)
            if isinstance(value, str) and value:
                parts.append(value)
        return self._extract_from_text("\n".join(parts))

    # -----------------------------------------------------------------
    # Polling
    # -----------------------------------------------------------------
    def wait_code(
        self,
        retries: int = 20,
        delay: float = 3,
        since_ts: float | None = None,
    ) -> str | None:
        since_ts = since_ts if since_ts is not None else time.time() - 5
        for i in range(1, retries + 1):
            for msg in reversed(self._fetch_messages_json()):
                ts = msg.get("timestamp") or msg.get("createdAt") or msg.get("date")
                if isinstance(ts, (int, float)) and ts < since_ts:
                    continue
                code = self._extract_from_payload(msg)
                if code:
                    print()
                    return code

            html = self._fetch_inbox_html()
            if self._debug and html:
                try:
                    with open(f"tempik_debug_{self.username}.html", "w", encoding="utf-8") as f:
                        f.write(html)
                except Exception:
                    pass

            if html:
                block_pattern = (
                    rf'data-address="{re.escape(self.email)}"'
                    rf'.*?inbox-card-count">(\d+)\s+emails'
                )
                bm = re.search(block_pattern, html, re.S)
                has_messages = True if not bm else int(bm.group(1)) > 0
                if has_messages:
                    code = self._extract_from_text(html)
                    if code:
                        print()
                        return code

            if i < retries:
                print(f"  {warn('...')} OTP ({i}/{retries})   ", end="\r", flush=True)
                time.sleep(delay)
        print()
        return None