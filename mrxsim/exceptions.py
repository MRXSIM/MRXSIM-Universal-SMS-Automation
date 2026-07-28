"""Custom exception hierarchy for the MRXSIM public API client."""

from __future__ import annotations

from typing import Any


class MrxsimError(Exception):
    """Base exception for all MRXSIM client errors."""

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        return self.message


class MrxsimConfigError(MrxsimError):
    """Raised when configuration is missing, invalid, or insecure."""


class MrxsimAuthError(MrxsimError):
    """Raised when the API key is missing, invalid, or unauthorized (HTTP 401/403)."""


class MrxsimAPIError(MrxsimError):
    """Raised for non-success HTTP responses from the MRXSIM API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.status_code = status_code


class MrxsimTimeoutError(MrxsimError):
    """Raised when an HTTP request or OTP poll exceeds the configured timeout."""


class MrxsimRateLimitError(MrxsimAPIError):
    """Raised when the API returns HTTP 429 (rate limited)."""


class MrxsimOrderError(MrxsimError):
    """Raised when an order ends in a terminal failure state."""

    def __init__(self, message: str, *, status: str | None = None) -> None:
        super().__init__(message, details={"status": status} if status else None)
        self.status = status
