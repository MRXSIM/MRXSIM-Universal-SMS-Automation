#!/usr/bin/env python3
"""Buy a virtual number via the MRXSIM package (no secrets in source)."""

from __future__ import annotations

import os
import sys

from mrxsim import Client, MrxsimConfigError, MrxsimError


def main() -> int:
    # Prefer environment variable; fall back to local config.json (gitignored).
    try:
        if os.environ.get("MRXSIM_API_KEY"):
            client = Client(
                country=os.environ.get("MRXSIM_COUNTRY", "england"),
                service=os.environ.get("MRXSIM_SERVICE", "telegram"),
                operator=os.environ.get("MRXSIM_OPERATOR", "any"),
            )
        else:
            client = Client.from_config("config.json")
    except MrxsimConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    try:
        with client:
            order = client.get_number()
    except MrxsimError as exc:
        print(f"Purchase failed: {exc}", file=sys.stderr)
        return 1

    print("Order created:")
    print(f"  id     : {order.get('id')}")
    print(f"  phone  : {order.get('phone_number')}")
    print(f"  price  : {order.get('price')}")
    print(f"  status : {order.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
