"""
MRXSIM synchronous HTTP client.

Authentication is never hardcoded. Provide credentials via:

* Environment variable ``MRXSIM_API_KEY``
* Explicit ``api_key=`` constructor argument
* A local config file (e.g. ``config.json``) loaded with :meth:`Client.from_config`

© MRXSIM · https://mrxsim.com
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin

import requests

from mrxsim.exceptions import (
    MrxsimAPIError,
    MrxsimAuthError,
    MrxsimConfigError,
    MrxsimError,
    MrxsimOrderError,
    MrxsimRateLimitError,
    MrxsimTimeoutError,
)

DEFAULT_BASE_URL = "https://mrxsim.com"
DEFAULT_USER_AGENT = "mrxsim-python/1.0.2 (+https://mrxsim.com)"
ENV_API_KEY = "MRXSIM_API_KEY"
ENV_BASE_URL = "MRXSIM_BASE_URL"

_TERMINAL_FAIL = frozenset({"CANCELED", "CANCELLED", "EXPIRED", "TIMEOUT", "FAILED"})

# Matches server OrderPublicOut — retail/zero-knowledge fields only.
PUBLIC_ORDER_FIELDS = frozenset(
    {
        "id",
        "phone_number",
        "service",
        "country",
        "status",
        "price",
        "sms_code",
    }
)


def _decode_field_token(encoded: str) -> str:
    """Decode an opaque field-name token (keeps deny-list literals out of source)."""
    return base64.b64decode(encoded.encode("ascii")).decode("ascii")


# Defense-in-depth: drop non-public response keys if a misconfigured upstream
# ever returns them. Tokens are opaque so vendor/metric names never appear in
# human-readable source.
_INTERNAL_FIELD_DENY = frozenset(
    _decode_field_token(token)
    for token in (
        "Y29zdF91c2R0",
        "Zml2ZXNpbV9vcmRlcl9pZA==",
        "bWFya3VwX211bHRpcGxpZXI=",
        "Zml2ZXNpbV9tYXJrdXBfbXVsdGlwbGllcg==",
        "aXNfYXBp",
        "cmVmdW5kZWQ=",
        "cHJvdmlkZXJfb3JkZXJfaWQ=",
        "d2hvbGVzYWxlX2Nvc3Q=",
        "d2hvbGVzYWxlX3ByaWNl",
    )
)
_VENDOR_PREFIX = _decode_field_token("Zml2ZXNpbQ==")
_COST_PREFIX = _decode_field_token("Y29zdF8=")
_MARKUP_TOKEN = _decode_field_token("bWFya3Vw")


def _require_nonempty(value: str | None, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise MrxsimConfigError(f"Missing required configuration: {field}")
    return text


def _normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


def load_config(path: str | Path) -> dict[str, Any]:
    """
    Load a JSON configuration file.

    The file must be a JSON object. ``api_key`` may be omitted if
    ``MRXSIM_API_KEY`` is set in the environment.

    Parameters
    ----------
    path:
        Filesystem path to the JSON config (e.g. ``config.json``).

    Returns
    -------
    dict[str, Any]
        Parsed configuration mapping.

    Raises
    ------
    MrxsimConfigError
        If the file is missing or not a valid JSON object.
    """
    cfg_path = Path(path).expanduser().resolve()
    if not cfg_path.is_file():
        raise MrxsimConfigError(
            f"Config file not found: {cfg_path}. "
            "Copy config.example.json → config.json and set your API key, "
            "or export MRXSIM_API_KEY."
        )
    try:
        with cfg_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise MrxsimConfigError(f"Invalid JSON in {cfg_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise MrxsimConfigError(f"Config file must be a JSON object: {cfg_path}")
    return data


class Client:
    """
    Production client for the MRXSIM.COM public SMS API.

    Supports every catalog service (Telegram, WhatsApp, Google, Instagram,
    PayPal, Snapchat, Other (SMS), and more).

    Parameters
    ----------
    api_key:
        MRXSIM API key. If omitted, read from ``MRXSIM_API_KEY``.
    base_url:
        API origin. Defaults to ``https://mrxsim.com`` or ``MRXSIM_BASE_URL``.
    country:
        Default catalog country code (e.g. ``england``, ``usa``, ``egypt``).
    service:
        Default service code (e.g. ``telegram``, ``whatsapp``, ``other``).
    operator:
        Default operator stack (``any`` or a specific stack id).
    timeout:
        Default HTTP request timeout in seconds.
    poll_interval:
        Default seconds between OTP polls.
    poll_timeout:
        Default maximum seconds to wait for an OTP.
    session:
        Optional pre-configured :class:`requests.Session`.

    Raises
    ------
    MrxsimConfigError
        If no API key can be resolved.
    MrxsimAuthError
        If the resolved key looks like an unreplaced placeholder.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        country: str | None = None,
        service: str | None = None,
        operator: str = "any",
        timeout: float = 30.0,
        poll_interval: float = 3.0,
        poll_timeout: float = 600.0,
        session: requests.Session | None = None,
    ) -> None:
        resolved_key = (api_key or os.environ.get(ENV_API_KEY) or "").strip()
        if not resolved_key:
            raise MrxsimConfigError(
                "API key required. Pass api_key=, set MRXSIM_API_KEY, "
                "or use Client.from_config('config.json'). "
                "Generate a key at https://mrxsim.com"
            )
        if resolved_key.startswith("REPLACE_") or resolved_key in {
            "mrxs_your_key_here",
            "YOUR_KEY",
            "changeme",
        }:
            raise MrxsimAuthError(
                "Placeholder API key detected. Set a real key from https://mrxsim.com"
            )

        env_base = os.environ.get(ENV_BASE_URL)
        self.base_url = _normalize_base_url(
            base_url or env_base or DEFAULT_BASE_URL
        )
        self.country = (country or "").strip().lower() or None
        self.service = (service or "").strip().lower() or None
        self.operator = ((operator or "any").strip().lower() or "any")
        self.timeout = max(5.0, float(timeout))
        self.poll_interval = max(1.0, float(poll_interval))
        self.poll_timeout = max(30.0, float(poll_timeout))

        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "X-API-Key": resolved_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": DEFAULT_USER_AGENT,
            }
        )
        # Never keep a public attribute that echoes the key.
        self._api_key_fingerprint = f"{resolved_key[:6]}…{resolved_key[-4:]}" if len(resolved_key) > 12 else "***"

    @classmethod
    def from_config(
        cls,
        path: str | Path = "config.json",
        *,
        session: requests.Session | None = None,
    ) -> Client:
        """
        Construct a client from a JSON config file.

        Environment variable ``MRXSIM_API_KEY`` overrides ``api_key`` in the file
        when set (prefer secrets outside the working tree).

        Parameters
        ----------
        path:
            Path to the JSON config file.
        session:
            Optional shared :class:`requests.Session`.
        """
        raw = load_config(path)
        api_key = os.environ.get(ENV_API_KEY) or str(raw.get("api_key") or "")
        return cls(
            api_key=api_key or None,
            base_url=str(raw.get("base_url") or DEFAULT_BASE_URL),
            country=str(raw.get("country") or "") or None,
            service=str(raw.get("service") or "") or None,
            operator=str(raw.get("operator") or "any"),
            timeout=float(raw.get("request_timeout_seconds") or 30),
            poll_interval=float(raw.get("poll_interval_seconds") or 3),
            poll_timeout=float(raw.get("poll_timeout_seconds") or 600),
            session=session,
        )

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _url(self, path: str) -> str:
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._session.request(
                method=method.upper(),
                url=self._url(path),
                json=dict(json_body) if json_body is not None else None,
                params=dict(params) if params is not None else None,
                timeout=timeout if timeout is not None else self.timeout,
            )
        except requests.Timeout as exc:
            raise MrxsimTimeoutError(f"HTTP request timed out: {method} {path}") from exc
        except requests.RequestException as exc:
            raise MrxsimError(f"HTTP transport error: {exc}") from exc
        return self._parse(response)

    @staticmethod
    def _sanitize_public_payload(body: dict[str, Any]) -> dict[str, Any]:
        """Keep only public retail fields; drop internal operational keys."""
        cleaned: dict[str, Any] = {}
        for key, value in body.items():
            lower = str(key).lower()
            if lower in _INTERNAL_FIELD_DENY:
                continue
            if lower.startswith(_VENDOR_PREFIX) or lower.startswith(_COST_PREFIX):
                continue
            if _MARKUP_TOKEN in lower and lower != "price":
                continue
            cleaned[key] = value
        return cleaned

    @staticmethod
    def _parse(response: requests.Response) -> dict[str, Any]:
        try:
            body: Any = response.json()
        except ValueError:
            body = {"error": (response.text or "")[:300]}

        if response.status_code in {401, 403}:
            detail = body.get("detail") if isinstance(body, dict) else body
            raise MrxsimAuthError(
                f"Authentication failed (HTTP {response.status_code}): {detail}",
                details=detail,
            )
        if response.status_code == 429:
            detail = body.get("detail") if isinstance(body, dict) else body
            raise MrxsimRateLimitError(
                f"Rate limited (HTTP 429): {detail}",
                status_code=429,
                details=detail,
            )
        if response.status_code >= 400:
            detail: Any
            if isinstance(body, dict):
                raw_detail = body.get("detail", body)
                if isinstance(raw_detail, dict):
                    detail = raw_detail.get("error") or raw_detail
                else:
                    detail = raw_detail
            else:
                detail = body
            raise MrxsimAPIError(
                f"HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
                details=detail,
            )
        if not isinstance(body, dict):
            raise MrxsimAPIError(
                "Unexpected API response (expected JSON object)",
                status_code=response.status_code,
                details=body,
            )
        return Client._sanitize_public_payload(body)

    def get_number(
        self,
        *,
        country: str | None = None,
        service: str | None = None,
        operator: str | None = None,
    ) -> dict[str, Any]:
        """
        Purchase a virtual number for a country/service pair.

        Parameters
        ----------
        country:
            Catalog country. Falls back to the client default.
        service:
            Catalog service. Falls back to the client default.
        operator:
            Operator stack. Falls back to the client default (``any``).

        Returns
        -------
        dict[str, Any]
            Order payload including ``id``, ``phone_number``, ``price``, ``status``.
        """
        resolved_country = _require_nonempty(country or self.country, "country")
        resolved_service = _require_nonempty(service or self.service, "service")
        resolved_operator = (
            (operator if operator is not None else self.operator) or "any"
        ).strip().lower() or "any"

        return self._request(
            "POST",
            "/api/v1/get_number",
            json_body={
                "country": resolved_country.lower(),
                "service": resolved_service.lower(),
                "operator": resolved_operator,
            },
        )

    def get_sms(self, order_id: str) -> dict[str, Any]:
        """
        Fetch the current SMS/OTP status for an order.

        Parameters
        ----------
        order_id:
            Order identifier returned by :meth:`get_number`.

        Returns
        -------
        dict[str, Any]
            Status payload; may include ``sms_code`` when received.
        """
        oid = _require_nonempty(order_id, "order_id")
        return self._request(
            "GET",
            "/api/v1/get_sms",
            params={"order_id": oid},
        )

    def wait_for_sms(
        self,
        order_id: str,
        *,
        poll_interval: float | None = None,
        poll_timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Poll until an OTP is received or the order fails / times out.

        Parameters
        ----------
        order_id:
            Order identifier from :meth:`get_number`.
        poll_interval:
            Seconds between polls (default: client ``poll_interval``).
        poll_timeout:
            Maximum wait in seconds (default: client ``poll_timeout``).

        Returns
        -------
        dict[str, Any]
            Final SMS payload containing ``sms_code`` when successful.

        Raises
        ------
        MrxsimOrderError
            If the order reaches a terminal failure status.
        MrxsimTimeoutError
            If no OTP arrives before ``poll_timeout``.
        """
        oid = _require_nonempty(order_id, "order_id")
        interval = max(1.0, float(poll_interval if poll_interval is not None else self.poll_interval))
        deadline = time.monotonic() + max(
            30.0, float(poll_timeout if poll_timeout is not None else self.poll_timeout)
        )

        while time.monotonic() < deadline:
            time.sleep(interval)
            row = self.get_sms(oid)
            status = str(row.get("status") or "").upper()
            code = str(row.get("sms_code") or "").strip()
            if code or status == "RECEIVED":
                return row
            if status in _TERMINAL_FAIL:
                raise MrxsimOrderError(
                    f"Order {oid} ended with status={status}",
                    status=status,
                )

        raise MrxsimTimeoutError(
            f"Timed out waiting for SMS on order {oid}"
        )

    def buy_and_wait(
        self,
        *,
        country: str | None = None,
        service: str | None = None,
        operator: str | None = None,
        poll_interval: float | None = None,
        poll_timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Purchase a number and block until the OTP arrives.

        Returns
        -------
        dict[str, Any]
            Combined result with ``order``, ``phone_number``, ``sms_code``, and ``status``.
        """
        order = self.get_number(country=country, service=service, operator=operator)
        order_id = str(order.get("id") or "")
        if not order_id:
            raise MrxsimAPIError("Purchase succeeded but no order id was returned", details=order)
        sms = self.wait_for_sms(
            order_id,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
        )
        return {
            "order": order,
            "order_id": order_id,
            "phone_number": sms.get("phone_number") or order.get("phone_number"),
            "sms_code": str(sms.get("sms_code") or "").strip(),
            "status": sms.get("status") or order.get("status"),
            "sms": sms,
        }

    def __repr__(self) -> str:
        return (
            f"Client(base_url={self.base_url!r}, "
            f"country={self.country!r}, service={self.service!r}, "
            f"key={self._api_key_fingerprint!r})"
        )


# Backwards-compatible alias used by early automation scripts.
MrxsimClient = Client
