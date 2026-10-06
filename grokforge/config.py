"""Configuration loaded from environment variables."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


# -------------------------------------------------------------------
# Temp mail
# -------------------------------------------------------------------
TEMPMAIL_PROVIDER = os.getenv("TEMPMAIL_PROVIDER", "tempik").lower()

# Tempik provider settings
TEMPIK_BASE    = os.getenv("TEMPIK_BASE", "https://tempik.neroism.web.id")
TEMPIK_DOMAINS = _split_csv(os.getenv("TEMPIK_DOMAINS", "neroism.web.id"))
TEMPIK_DEBUG   = os.getenv("TEMPIK_DEBUG", "0") == "1"

# Generic settings shared across providers
# (a provider-specific module reads these if needed)
DEFAULT_EMAIL_DOMAINS = TEMPIK_DOMAINS  # fallback for providers without own list

# -------------------------------------------------------------------
# xAI
# -------------------------------------------------------------------
DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "LauSapeEmpruy88@@")

# -------------------------------------------------------------------
# 9router
# -------------------------------------------------------------------
ROUTER_BASE       = os.getenv("ROUTER_BASE", "http://localhost:20128").rstrip("/")
ROUTER_PASSWORD   = os.getenv("ROUTER_PASSWORD", "123456")
ROUTER_AUTH_TOKEN = os.getenv("ROUTER_AUTH_TOKEN", "")
ROUTER_TOKEN_FILE = os.getenv("ROUTER_TOKEN_FILE", ".9router_token.json")

# -------------------------------------------------------------------
# Concurrency
# -------------------------------------------------------------------
DEFAULT_THREADS = int(os.getenv("DEFAULT_THREADS", "1") or 1)

# -------------------------------------------------------------------
# Static data
# -------------------------------------------------------------------
FIRST_NAMES = [
    "Ahmad", "Rafi", "Dimas", "Budi", "Andi", "Sari", "Putri", "Dewi",
    "Agus", "Eka", "Rizky", "Fajar", "Bayu", "Yudi", "Tono", "Wawan",
    "Indah", "Rina", "Ayu", "Kartika", "Mega", "Nanda", "Citra", "Lestari",
    "Hendra", "Joko", "Taufik", "Arif", "Yusuf", "Nurul", "Fitri", "Melati",
    "Hani", "Dian", "Rizal", "Slamet", "Surya", "Galih", "Farhan", "Rizwan",
    "Sinta", "Maya", "Novi", "Rosa", "Yani", "Tia", "Dianita", "Rizka",
    "Rachma", "Anisa",
]

LAST_NAMES = [
    "Udin", "Pratama", "Saputra", "Wijaya", "Nugraha", "Santoso",
    "Hidayat", "Gunawan", "Susanto", "Mahendra", "Setiawan", "Firmansyah",
    "Syahputra", "Ramadhan", "Permana", "Sutrisno", "Wibowo", "Suryadi",
    "Kurniawan", "Subekti", "Suharto", "Basuki", "Purnomo", "Iskandar",
    "Halim", "Nasution", "Lubis", "Simanjuntak", "Hutagalung", "Siregar",
    "Manullang", "Sinaga", "Panjaitan", "Sitompul", "Tambunan", "Hutapea",
    "Ginting", "Tarigan", "Sembiring", "Purba", "Saragih", "Pakpahan",
    "Nainggolan", "Hutasoit", "Pasaribu", "Tobing", "Sihombing", "Malau",
    "LumbanGaol", "Hutajulu",
]

OTP_FALSE = {
    "FAFAFA", "ABCDEF", "123456", "000000", "111111", "989898",
    "FFFFFF", "AAAAAA", "QQQQQQ", "XXXXXX", "SCRIPT", "STYLE",
    "BUTTON", "OBJECT", "WINDOW", "DOCUMENT", "NUMBER", "STRING",
    "RETURN", "IMPORT", "EXPORT", "LENGTH", "SOURCE", "TARGET",
    "FOOTER", "HEADER", "NAVBAR", "BANNER", "SIDEBAR", "LOGOUT",
    "LOGIN",  "SIGNUP", "SIGNIN", "MENU",   "SEARCH", "SUBMIT",
    "CANCEL", "DELETE", "ARCHIVE", "REPORT", "REPLY",  "FORWARD",
}