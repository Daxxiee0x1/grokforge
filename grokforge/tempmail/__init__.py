"""
Temp mail provider registry and factory.

Usage
-----
    from grokforge.tempmail import get_provider

    ProviderClass = get_provider()          # uses TEMPMAIL_PROVIDER from .env
    inbox = ProviderClass()                 # random address
    inbox.create_inbox()
    code = inbox.wait_code()

Adding a new provider
---------------------
    1. Create grokforge/tempmail/providers/<name>.py
    2. Subclass BaseTempMail and decorate the class with @register("<name>")
    3. Import the module in grokforge/tempmail/providers/__init__.py
    4. Set TEMPMAIL_PROVIDER=<name> in .env
"""
from __future__ import annotations

from typing import Type

from ..config import TEMPMAIL_PROVIDER
from .base import BaseTempMail

# Populate the registry by importing provider modules.
from . import providers  # noqa: F401  (side-effect import)


_REGISTRY: dict[str, Type[BaseTempMail]] = {}


def register(name: str):
    """Class decorator to register a temp mail provider under a name."""
    def wrapper(cls: Type[BaseTempMail]) -> Type[BaseTempMail]:
        _REGISTRY[name.lower()] = cls
        return cls
    return wrapper


def available_providers() -> list[str]:
    """Return the names of all registered providers."""
    return sorted(_REGISTRY.keys())


def get_provider(name: str | None = None) -> Type[BaseTempMail]:
    """
    Return the provider class registered under ``name``.
    If ``name`` is None, uses TEMPMAIL_PROVIDER from .env.
    """
    key = (name or TEMPMAIL_PROVIDER or "").lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"Unknown temp mail provider: {key!r}. "
            f"Available: {available_providers()}"
        )
    return _REGISTRY[key]


__all__ = [
    "BaseTempMail",
    "register",
    "get_provider",
    "available_providers",
]