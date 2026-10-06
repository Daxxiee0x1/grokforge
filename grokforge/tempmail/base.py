"""Abstract base class for temp mail providers."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseTempMail(ABC):
    """
    Contract for a temp mail provider.

    A concrete provider must:
      * expose ``email`` - the full address (local part + domain)
      * implement ``create_inbox`` to register the address with the service
      * implement ``wait_code`` to poll the inbox until an OTP is found

    Optional helper attributes:
      * ``username`` / ``domain`` split from ``email``
    """

    def __init__(self, email: str | None = None):
        # Concrete providers should set self.email to a random address
        # when ``email`` is None, then split it into username / domain.
        if email is None:
            raise NotImplementedError(
                "Subclass must generate a random email when none is given."
            )
        self.email = email
        self.username, _, self.domain = email.partition("@")

    # -----------------------------------------------------------------
    # Required API
    # -----------------------------------------------------------------
    @abstractmethod
    def create_inbox(self) -> bool:
        """Register the inbox with the provider. Return True on success."""
        raise NotImplementedError

    @abstractmethod
    def wait_code(
        self,
        retries: int = 20,
        delay: float = 3,
        since_ts: float | None = None,
    ) -> str | None:
        """
        Poll the inbox for a verification code.

        :param retries: maximum number of poll attempts
        :param delay:   seconds between attempts
        :param since_ts: only consider messages received after this
                         Unix timestamp (filters stale messages)
        :return: the extracted code, or None if not found
        """
        raise NotImplementedError