"""
Public API of the tempmail package.

Importing this module triggers loading of every provider module,
which registers them with the registry.

Usage
-----
    from grokforge.tempmail import get_provider

    ProviderClass = get_provider()     # uses TEMPMAIL_PROVIDER from .env
    inbox = ProviderClass()
    inbox.create_inbox()
    code = inbox.wait_code()

Adding a new provider
---------------------
    1. Create grokforge/tempmail/providers/<name>.py
    2. Subclass BaseTempMail and decorate the class with @register("<name>")
       (import register from grokforge.tempmail.registry)
    3. Import the module in grokforge/tempmail/providers/__init__.py
    4. Set TEMPMAIL_PROVIDER=<name> in .env
"""
from __future__ import annotations

from typing import Type

from ..config import TEMPMAIL_PROVIDER
from .base import BaseTempMail
from .registry import register, available_providers, get_provider_class

# Side-effect import: loads every provider module and populates the registry.
from . import providers  # noqa: F401,E402


def get_provider(name: str | None = None) -> Type[BaseTempMail]:
    """
    Return the provider class for ``name``, or for TEMPMAIL_PROVIDER
    from the .env file when ``name`` is None.
    """
    key = (name or TEMPMAIL_PROVIDER or "").lower()
    return get_provider_class(key)


__all__ = [
    "BaseTempMail",
    "register",
    "get_provider",
    "available_providers",
]