"""
Provider registry for temp mail backends.

This module must not import anything from the tempmail package
to avoid circular imports. Provider modules import `register`
from here, and `__init__.py` imports `get_provider` from here.
"""
from __future__ import annotations

from typing import Type

from .base import BaseTempMail


_REGISTRY: dict[str, Type[BaseTempMail]] = {}


def register(name: str):
    """Class decorator that registers a temp mail provider under ``name``."""
    def wrapper(cls: Type[BaseTempMail]) -> Type[BaseTempMail]:
        _REGISTRY[name.lower()] = cls
        return cls
    return wrapper


def available_providers() -> list[str]:
    """Return the names of all registered providers, sorted."""
    return sorted(_REGISTRY.keys())


def get_provider_class(name: str) -> Type[BaseTempMail]:
    """Return the provider class registered under ``name``."""
    key = (name or "").lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"Unknown temp mail provider: {key!r}. "
            f"Available: {available_providers()}"
        )
    return _REGISTRY[key]