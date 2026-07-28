"""
MRXSIM — Official Python client for https://mrxsim.com

Secure SMS number purchasing and OTP retrieval for every MRXSIM catalog service.
"""

from __future__ import annotations

from mrxsim.client import (
    PUBLIC_ORDER_FIELDS,
    Client,
    MrxsimClient,
    load_config,
)
from mrxsim.exceptions import (
    MrxsimAPIError,
    MrxsimAuthError,
    MrxsimConfigError,
    MrxsimError,
    MrxsimOrderError,
    MrxsimRateLimitError,
    MrxsimTimeoutError,
)

__all__ = [
    "Client",
    "MrxsimClient",
    "PUBLIC_ORDER_FIELDS",
    "load_config",
    "MrxsimError",
    "MrxsimConfigError",
    "MrxsimAuthError",
    "MrxsimAPIError",
    "MrxsimTimeoutError",
    "MrxsimRateLimitError",
    "MrxsimOrderError",
]

__version__ = "1.0.2"
__author__ = "MRXSIM"
