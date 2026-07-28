"""Basic unit tests for mrxsim (no live network / no real API keys)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mrxsim import Client, MrxsimAuthError, MrxsimConfigError, __version__
from mrxsim.exceptions import MrxsimAPIError, MrxsimRateLimitError


def test_version() -> None:
    assert __version__ == "1.0.2"


def test_sanitize_strips_internal_keys() -> None:
    # Opaque tokens — same encoding as client deny-list (no plaintext vendor/metric names).
    import base64

    def _tok(encoded: str) -> str:
        return base64.b64decode(encoded.encode("ascii")).decode("ascii")

    internal_cost = _tok("Y29zdF91c2R0")
    upstream_vendor_id = _tok("Zml2ZXNpbV9vcmRlcl9pZA==")
    markup_key = _tok("bWFya3VwX211bHRpcGxpZXI=")
    api_flag = _tok("aXNfYXBp")

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "id": "ord_1",
        "phone_number": "+201000000000",
        "service": "telegram",
        "country": "egypt",
        "status": "PENDING",
        "price": "0.56",
        "sms_code": None,
        internal_cost: "0.21",
        upstream_vendor_id: "upstream-999",
        markup_key: "1.4",
        api_flag: True,
    }
    cleaned = Client._parse(response)
    assert cleaned["id"] == "ord_1"
    assert cleaned["price"] == "0.56"
    assert internal_cost not in cleaned
    assert upstream_vendor_id not in cleaned
    assert markup_key not in cleaned
    assert api_flag not in cleaned


def test_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MRXSIM_API_KEY", raising=False)
    with pytest.raises(MrxsimConfigError):
        Client()


def test_rejects_placeholder_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MRXSIM_API_KEY", raising=False)
    with pytest.raises(MrxsimAuthError):
        Client(api_key="REPLACE_WITH_YOUR_MRXSIM_API_KEY")


def test_from_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MRXSIM_API_KEY", raising=False)
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "api_key": "mrxs_test_key_abcdef123456",
                "base_url": "https://mrxsim.com",
                "country": "england",
                "service": "telegram",
                "operator": "any",
                "poll_interval_seconds": 3,
                "poll_timeout_seconds": 600,
                "request_timeout_seconds": 30,
            }
        ),
        encoding="utf-8",
    )
    client = Client.from_config(cfg)
    assert client.country == "england"
    assert client.service == "telegram"
    assert client.base_url == "https://mrxsim.com"
    client.close()


def test_env_overrides_config_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "api_key": "mrxs_file_key_should_not_win",
                "country": "usa",
                "service": "whatsapp",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MRXSIM_API_KEY", "mrxs_env_key_wins_abcdef")
    client = Client.from_config(cfg)
    # Fingerprint should reflect env key prefix, not file key.
    assert "mrxs_e" in repr(client)
    client.close()


def test_parse_rate_limit() -> None:
    response = MagicMock()
    response.status_code = 429
    response.json.return_value = {"detail": {"error": "slow down"}}
    with pytest.raises(MrxsimRateLimitError):
        Client._parse(response)


def test_parse_auth_error() -> None:
    response = MagicMock()
    response.status_code = 401
    response.json.return_value = {"detail": "invalid key"}
    with pytest.raises(MrxsimAuthError):
        Client._parse(response)


def test_get_number_posts_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MRXSIM_API_KEY", "mrxs_unit_test_key_xyz")
    client = Client(country="egypt", service="telegram")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "ord_1",
        "phone_number": "+201000000000",
        "price": "0.56",
        "status": "PENDING",
    }
    with patch.object(client._session, "request", return_value=mock_response) as req:
        order = client.get_number()
        assert order["id"] == "ord_1"
        kwargs = req.call_args.kwargs
        assert kwargs["method"] == "POST"
        assert kwargs["json"]["country"] == "egypt"
        assert kwargs["json"]["service"] == "telegram"
    client.close()


def test_get_number_missing_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MRXSIM_API_KEY", "mrxs_unit_test_key_xyz")
    client = Client()
    with pytest.raises(MrxsimConfigError):
        client.get_number()
    client.close()


def test_api_error_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MRXSIM_API_KEY", "mrxs_unit_test_key_xyz")
    response = MagicMock()
    response.status_code = 422
    response.json.return_value = {"detail": {"error": "no stock"}}
    with pytest.raises(MrxsimAPIError) as excinfo:
        Client._parse(response)
    assert excinfo.value.status_code == 422
