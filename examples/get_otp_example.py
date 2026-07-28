#!/usr/bin/env python3
"""Poll an existing order until the OTP arrives."""

from __future__ import annotations

import os
import sys

from mrxsim import Client, MrxsimConfigError, MrxsimError, MrxsimTimeoutError


def main() -> int:
    order_id = (os.environ.get("MRXSIM_ORDER_ID") or "").strip()
    if not order_id:
        if len(sys.argv) > 1:
            order_id = sys.argv[1].strip()
    if not order_id:
        print(
            "Usage: MRXSIM_ORDER_ID=<id> python examples/get_otp_example.py\n"
            "   or: python examples/get_otp_example.py <order_id>",
            file=sys.stderr,
        )
        return 2

    try:
        if os.environ.get("MRXSIM_API_KEY"):
            client = Client()
        else:
            client = Client.from_config("config.json")
    except MrxsimConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    try:
        with client:
            sms = client.wait_for_sms(order_id)
    except MrxsimTimeoutError as exc:
        print(f"Timeout: {exc}", file=sys.stderr)
        return 1
    except MrxsimError as exc:
        print(f"OTP poll failed: {exc}", file=sys.stderr)
        return 1

    print("SMS received:")
    print(f"  phone : {sms.get('phone_number')}")
    print(f"  code  : {sms.get('sms_code')}")
    print(f"  status: {sms.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
