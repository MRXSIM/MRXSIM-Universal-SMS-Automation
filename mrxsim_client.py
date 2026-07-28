#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy CLI entrypoint — thin wrapper around the ``mrxsim`` package.

Prefer::

    pip install mrxsim
    python -c "from mrxsim import Client; ..."

Or::

    export MRXSIM_API_KEY=...
    python examples/buy_number_example.py

© MRXSIM · https://mrxsim.com
"""

from __future__ import annotations

import sys
import time

try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init(autoreset=True)
except ImportError:  # pragma: no cover

    class _NoColor:
        GREEN = CYAN = YELLOW = RED = RESET_ALL = ""

    Fore = Style = _NoColor()  # type: ignore[assignment]

from mrxsim import Client
from mrxsim.exceptions import MrxsimError, MrxsimOrderError, MrxsimTimeoutError

BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ███╗   ███╗██████╗ ██╗  ██╗███████╗██╗███╗   ███╗     ║
║   ████╗ ████║██╔══██╗╚██╗██╔╝██╔════╝██║████╗ ████║     ║
║   ██╔████╔██║██████╔╝ ╚███╔╝ ███████╗██║██╔████╔██║     ║
║   ██║╚██╔╝██║██╔══██╗ ██╔██╗ ╚════██║██║██║╚██╔╝██║     ║
║   ██║ ╚═╝ ██║██║  ██║██╔╝ ██╗███████║██║██║ ╚═╝ ██║     ║
║   ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝╚═╝     ╚═╝     ║
║                                                          ║
║          SMS AUTOMATION  ·  mrxsim.com                   ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""


def _print_status(msg: str, *, tone: str = "info") -> None:
    ts = time.strftime("%H:%M:%S")
    color = {
        "info": Fore.CYAN,
        "ok": Fore.GREEN,
        "warn": Fore.YELLOW,
        "err": Fore.RED,
    }.get(tone, Fore.CYAN)
    print(f"{color}[{ts}] {msg}{Style.RESET_ALL}", flush=True)


def run() -> int:
    print(f"{Fore.GREEN}{BANNER}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  Official automation client for MRXSIM.COM{Style.RESET_ALL}")
    print("  Use MRXSIM_API_KEY or gitignored config.json — never hardcode secrets.\n")

    try:
        client = Client.from_config("config.json")
    except MrxsimError as exc:
        print(f"{Fore.RED}CONFIG ERROR: {exc}{Style.RESET_ALL}")
        return 2

    _print_status(
        f"Target → country={client.country} service={client.service} operator={client.operator}"
    )

    try:
        order = client.get_number()
    except MrxsimError as exc:
        _print_status(f"Purchase failed: {exc}", tone="err")
        client.close()
        return 1

    order_id = str(order.get("id") or "")
    phone = order.get("phone_number") or "—"
    _print_status(
        f"Order {order_id} | phone={phone} | price={order.get('price')} | status={order.get('status')}",
        tone="ok",
    )
    if not order_id:
        _print_status("No order id returned.", tone="err")
        client.close()
        return 1

    try:
        row = client.wait_for_sms(order_id)
    except MrxsimTimeoutError:
        _print_status("Timeout waiting for SMS.", tone="err")
        return 1
    except MrxsimOrderError as exc:
        _print_status(str(exc), tone="err")
        return 1
    except MrxsimError as exc:
        _print_status(f"Poll failed: {exc}", tone="err")
        return 1
    finally:
        client.close()

    code = str(row.get("sms_code") or "").strip()
    _print_status(f"SMS RECEIVED → {code or '(empty code field)'}", tone="ok")
    print(f"\n{Fore.GREEN}── RESULT ─────────────────────────────{Style.RESET_ALL}")
    print(f"  phone : {row.get('phone_number') or phone}")
    print(f"  code  : {code}")
    print(f"  order : {order_id}")
    print(f"{Fore.GREEN}───────────────────────────────────────{Style.RESET_ALL}\n")
    print(f"{Fore.CYAN}Powered by MRXSIM.COM{Style.RESET_ALL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
