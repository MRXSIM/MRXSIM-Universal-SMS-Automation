# mrxsim

Official Python client for **[MRXSIM.COM](https://mrxsim.com)** — purchase virtual numbers and retrieve SMS OTPs for every catalog service (Telegram, WhatsApp, Google, Instagram, PayPal, Snapchat, Other (SMS), and more).

> Brand: **MRXSIM** · Domain: **https://mrxsim.com** · Package: **`mrxsim`**

---

## Security first

- **No hardcoded API keys** in library source or examples.
- Prefer environment variable ``MRXSIM_API_KEY``.
- Or load a local ``config.json`` that is **gitignored**.
- Never commit live keys. Revoke immediately if exposed.

---

## Install

```bash
pip install mrxsim
```

From this repository (editable):

```bash
pip install -e .
```

---

## Quick start (environment variable)

```bash
export MRXSIM_API_KEY="mrxs_your_key_here"   # Linux / macOS
# setx MRXSIM_API_KEY "mrxs_your_key_here"  # Windows (new shell)
```

```python
from mrxsim import Client

with Client(country="england", service="telegram") as client:
    order = client.get_number()
    print(order["phone_number"], order["id"])

    sms = client.wait_for_sms(order["id"])
    print(sms["sms_code"])
```

One-shot purchase + OTP:

```python
from mrxsim import Client

with Client(country="egypt", service="whatsapp") as client:
    result = client.buy_and_wait()
    print(result["phone_number"], result["sms_code"])
```

---

## Quick start (config file)

```bash
cp config.example.json config.json
# edit config.json → set api_key, country, service
```

```python
from mrxsim import Client

client = Client.from_config("config.json")
order = client.get_number()
sms = client.wait_for_sms(order["id"])
client.close()
```

``MRXSIM_API_KEY`` overrides ``api_key`` in the file when set.

---

## Get your API key

1. Open [https://mrxsim.com](https://mrxsim.com) and create an account.
2. Top up with **Crypto** (USDT / supported networks).
3. **Profile → Get API KEY** (shown once at create/regenerate).
4. Export ``MRXSIM_API_KEY`` or paste into gitignored ``config.json``.

---

## API surface

| Method | Endpoint | Client method |
|--------|----------|---------------|
| `POST` | `/api/v1/get_number` | `Client.get_number()` |
| `GET` | `/api/v1/get_sms?order_id=…` | `Client.get_sms()` / `wait_for_sms()` |

Header on every call:

```http
X-API-Key: YOUR_KEY
```

### Public order fields (zero-knowledge)

Successful responses expose **retail** fields only — aligned with the MRXSIM
server `OrderPublicOut` contract:

| Field | Meaning |
|-------|---------|
| `id` | MRXSIM order UUID |
| `phone_number` | Assigned number |
| `service` / `country` | Catalog codes |
| `status` | Order status |
| `price` | Retail USDT price charged |
| `sms_code` | OTP when received |

Internal operational metrics and upstream routing identifiers are **not** part
of the public API. The client also sanitizes responses client-side if any such
fields ever appear (defense in depth).

Docs: [https://mrxsim.com/docs](https://mrxsim.com/docs)

---

## Changelog

### 1.0.2

- Sanitize client responses to strip internal operational metrics and upstream routing identifiers.
- Harden public documentation for white-label / zero-knowledge API alignment.
- User-Agent bumped to `mrxsim-python/1.0.2`.

### 1.0.1

- Document and enforce zero-knowledge public order fields.
- User-Agent bumped to `mrxsim-python/1.0.1`.

---

## Examples

```bash
export MRXSIM_API_KEY="…"
python examples/buy_number_example.py
python examples/get_otp_example.py <order_id>
```

---

## Development

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m build
```

---

## Support

- Site: [https://mrxsim.com](https://mrxsim.com)
- Docs: [https://mrxsim.com/docs](https://mrxsim.com/docs)
- Issues: [GitHub](https://github.com/MRXSIM/MRXSIM-Universal-SMS-Automation/issues)

© MRXSIM · Secure SMS Infrastructure
