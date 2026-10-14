#!/usr/bin/env python3
"""
NinjaView connection checker — find which link of
    TradingView alert → NinjaView webhook → NinjaView add-on → NinjaTrader
is dropping orders.

    # 1. Check a message (paste it from TradingView's alert log)
    python tools/ninjaview_check.py lint '{"alert":"market buy","account":"Sim101","ticker":"MNQ 12-26","qty":"1"}'

    # 2. Send a test order straight to NinjaView, skipping TradingView
    python tools/ninjaview_check.py send --url <your NinjaView webhook URL> \
        --account Sim101 --instrument "MNQ 12-26" buy
    python tools/ninjaview_check.py send --url ... --account Sim101 --instrument "MNQ 12-26" close

    # or send an exact message
    python tools/ninjaview_check.py send --url ... --message '<json>'

If step 2 places an order in NinjaTrader but your TradingView alert doesn't,
the problem is on the TradingView side (webhook URL, 2FA, alert message).
If step 2 doesn't place an order either, it's on the NinjaView/NinjaTrader side.

Standard library only. The webhook URL can also come from $NINJAVIEW_URL.
Treat that URL like a password: anyone who has it can trade your accounts.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date

# `alert` values from NinjaView's help page (ninja-view.com/help, "Payload Syntax").
ENTRY_ALERTS = {
    "market buy", "market sell", "copy market buy", "copy market sell",
    "oco market buy", "oco market sell", "limit buy", "limit sell",
    "oco limit buy", "oco limit sell", "stopmarket buy", "stopmarket sell",
    "stoplimit buy", "stoplimit sell",
    "close then market buy", "close then market sell",
    "close then oco market buy", "close then oco market sell",
    "close then oco limit buy", "close then oco limit sell",
    "atm strategy market buy", "atm strategy market sell",
    "atm strategy limit buy", "atm strategy limit sell",
    "close then atm strategy market buy", "close then atm strategy market sell",
}
NO_QTY_ALERTS = {
    "market close", "market flat", "flatten account", "cancel oco",
    "cancel oco and flatten", "adjusted oco", "exit stopmarket", "stop atm strategy",
}
KNOWN_ALERTS = ENTRY_ALERTS | NO_QTY_ALERTS
PRICE_FIELDS = ("limit_price", "stop_price", "take_profit_price", "stop_loss_price")
TIF_VALUES = {"DAY", "GTC", "IOC", "FOK"}
NT_TICKER = re.compile(r"^([A-Z0-9]+) (\d{2})-(\d{2})$")          # MNQ 12-26
OLD_NT_TICKER = re.compile(r"^[A-Z0-9]+ [A-Z]{3}\d{2}$")          # NQ SEP24

FAIL, WARN, OK = "FAIL", "WARN", "ok"


def lint(message: str, today: date | None = None) -> list[tuple[str, str]]:
    """Return (level, text) findings for a NinjaView alert message."""
    today = today or date.today()
    out: list[tuple[str, str]] = []

    if any(c in message for c in "“”‘’"):
        out.append((FAIL, "Curly quotes (“ ” ‘ ’) found. Copying from a web page or Word does this. Retype them as straight quotes \"."))
    if re.search(r"%[a-z_]+%", message):
        out.append((FAIL, f"Unfilled connection-test token(s): {', '.join(sorted(set(re.findall(r'%[a-z_]+%', message))))}"))
    if "{{" in message:
        out.append((WARN, "Contains TradingView {{placeholders}}. TradingView fills them only inside an alert, so those fields aren't checked here."
                          " Lint the filled-in message from the alert log instead; sent any other way they arrive as literal text."))

    try:
        data = json.loads(message)
    except json.JSONDecodeError as e:
        hint = ""
        if re.search(r",\s*[}\]]", message):
            hint = " There's a trailing comma before a closing } or ]."
        elif "'" in message and '"' not in message:
            hint = " JSON needs double quotes, not single quotes."
        out.append((FAIL, f"Not valid JSON ({e.msg} at character {e.pos}).{hint} NinjaView can't read the message."))
        return out
    if not isinstance(data, dict):
        out.append((FAIL, "Message must be a JSON object: { ... }."))
        return out

    # Fields still holding {{placeholders}} or %tokens% were reported above; don't check their values.
    def unfilled(key: str) -> bool:
        v = data.get(key)
        return isinstance(v, str) and ("{{" in v or re.search(r"%[a-z_]+%", v) is not None)

    # alert
    alert = data.get("alert")
    alert_key = alert.strip().lower() if isinstance(alert, str) else None
    if unfilled("alert"):
        alert_key = None
    elif not alert_key:
        out.append((FAIL, 'Missing "alert" (the order command, e.g. "market buy").'))
    elif alert_key not in KNOWN_ALERTS:
        out.append((WARN, f'"alert": "{alert}" is not on NinjaView\'s list of commands. Check the spelling (e.g. "market buy", "market close").'))
    else:
        out.append((OK, f'alert "{alert}"'))

    # account
    account = data.get("account")
    if unfilled("account"):
        pass
    elif not isinstance(account, str) or not account.strip():
        out.append((FAIL, 'Missing "account" (NinjaTrader account Name, e.g. "Sim101").'))
    else:
        names = [a.strip() for a in account.split(",")]
        if any(not n for n in names):
            out.append((FAIL, f'"account": "{account}" has an empty name (stray comma).'))
        elif account != account.strip():
            out.append((WARN, f'"account" has leading/trailing spaces: "{account}". It must match NinjaTrader exactly.'))
        else:
            out.append((OK, f"account(s) {', '.join(names)}"))
        live = [n for n in names if n and not n.lower().startswith("sim")]
        if live:
            out.append((WARN, f"Not a Sim account: {', '.join(live)}. Orders will be real. Prop-firm accounts must use the Name column, not Display Name."))

    # ticker
    ticker = data.get("ticker")
    if unfilled("ticker"):
        pass
    elif not isinstance(ticker, str) or not ticker.strip():
        out.append((FAIL, 'Missing "ticker" (NinjaTrader instrument, e.g. "MNQ 12-26").'))
    elif "!" in ticker or ":" in ticker:
        out.append((FAIL, f'"ticker": "{ticker}" is a TradingView symbol. NinjaTrader needs ROOT MM-YY, e.g. "MNQ 12-26".'))
    elif m := NT_TICKER.match(ticker):
        month, year = int(m.group(2)), 2000 + int(m.group(3))
        if not 1 <= month <= 12:
            out.append((FAIL, f'"ticker": "{ticker}" has month {month:02d}.'))
        elif (year, month) < (today.year, today.month):
            out.append((FAIL, f'"ticker": "{ticker}" is an expired contract. Use the current front month.'))
        elif (year, month) == (today.year, today.month):
            out.append((WARN, f'"ticker": "{ticker}" expires this month. Check volume hasn\'t already rolled to the next contract.'))
        else:
            out.append((OK, f"ticker {ticker}"))
    elif OLD_NT_TICKER.match(ticker):
        out.append((WARN, f'"ticker": "{ticker}" uses the old "NQ SEP24" style. NinjaTrader 8 names contracts ROOT MM-YY, e.g. "MNQ 12-26".'))
    else:
        out.append((WARN, f'"ticker": "{ticker}" doesn\'t look like ROOT MM-YY (e.g. "MNQ 12-26").'))

    # qty
    qty = data.get("qty")
    if unfilled("qty"):
        pass
    elif qty is None:
        if alert_key in ENTRY_ALERTS:
            out.append((FAIL, f'Missing "qty" (required for "{alert}").'))
    elif isinstance(qty, bool) or not re.fullmatch(r"\d+", str(qty)) or int(qty) < 1:
        out.append((FAIL, f'"qty": {json.dumps(qty)} must be a whole number of at least 1.'))
    else:
        out.append((OK, f"qty {qty}"))

    # prices and per-command requirements
    for f in PRICE_FIELDS:
        if f in data and not unfilled(f):
            v = str(data[f])
            if "," in v:
                out.append((FAIL, f'"{f}": "{v}" contains a comma. Use a period for decimals and no thousands separator.'))
            else:
                try:
                    float(v)
                except ValueError:
                    out.append((FAIL, f'"{f}": "{v}" is not a number.'))
    if alert_key:
        need = []
        if "limit" in alert_key:
            need.append("limit_price")
        if "stopmarket" in alert_key or "stoplimit" in alert_key:
            need.append("stop_price")
        if "oco" in alert_key and alert_key in ENTRY_ALERTS:
            need += ["take_profit_price", "stop_loss_price"]
        if "atm strategy" in alert_key and alert_key != "stop atm strategy":
            need.append("strategy")
        for f in need:
            if f not in data:
                out.append((FAIL, f'"{alert}" needs "{f}".'))

    if "tif" in data and str(data["tif"]).upper() not in TIF_VALUES:
        out.append((FAIL, f'"tif": "{data["tif"]}" must be one of {", ".join(sorted(TIF_VALUES))}.'))
    if "delay" in data:
        try:
            if not 0 <= int(data["delay"]) <= 10000:
                raise ValueError
        except (TypeError, ValueError):
            out.append((FAIL, f'"delay": {json.dumps(data["delay"])} must be 0–10000 (milliseconds).'))

    return out


def print_findings(findings: list[tuple[str, str]]) -> bool:
    """Print findings; return True when there is no FAIL."""
    for level, text in findings:
        print(f"  {level:>4}  {text}")
    fails = sum(level == FAIL for level, _ in findings)
    warns = sum(level == WARN for level, _ in findings)
    print(f"  => {'FAIL' if fails else 'PASS'}  ({fails} problem(s), {warns} warning(s))")
    return fails == 0


def build_message(action: str, account: str, instrument: str, qty: int) -> str:
    payload = {"alert": f"market {action}", "account": account, "ticker": instrument}
    if action != "close":
        payload["qty"] = str(qty)
    return json.dumps(payload, separators=(",", ":"))


def send(url: str, message: str, timeout: float) -> int:
    """POST the message the way TradingView does; explain what the result means."""
    req = urllib.request.Request(
        url, data=message.encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "ninjaview-check/1.0"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, body = resp.status, resp.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read(2000).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        print(f"  Could not reach {redact(url)}: {reason}")
        if re.match(r"https?://(127\.0\.0\.1|localhost)", url):
            print("  -> The local add-on isn't listening. NinjaTrader must be open with the NinjaView add-on window")
            print("     running, and this command must run on the same PC.")
        else:
            print("  -> Check the URL is copied completely from NinjaView's Webhook Setup page. If you clicked")
            print("     Rotate there, the old URL stopped working.")
        return 2
    ms = (time.monotonic() - started) * 1000
    print(f"  HTTP {status} in {ms:.0f} ms")
    if body.strip():
        print(f"  Response: {body.strip()[:500]}")

    if 200 <= status < 300:
        print("  -> NinjaView accepted the message. Now check NinjaTrader (Orders / Executions tab) for the order.")
        print("     Order there: NinjaView works, so if TradingView alerts still don't trade, the problem is on")
        print("       the TradingView side: Webhook URL not ticked or out of date, 2FA off, or the alert message.")
        print("     No order there: the problem is between NinjaView and NinjaTrader. Check the add-on shows")
        print("       Connected, Auto-Trade is on, and the account/instrument match NinjaTrader exactly.")
        return 0
    if status in (401, 403, 404, 410):
        print("  -> The URL was rejected. It's wrong, out of date (rotated) or your license isn't active.")
    elif status in (400, 422):
        print("  -> NinjaView rejected the message format. Run `lint` on it and compare it with NinjaView's payload docs.")
    else:
        print("  -> Unexpected response. Send the output above to support@ninja-view.com.")
    return 1


def redact(url: str) -> str:
    """Hide the secret part of a webhook URL in printed output."""
    if re.match(r"https?://(127\.0\.0\.1|localhost)", url):
        return url
    return re.sub(r"([^/]{6})[^/]{6,}$", r"\1…", url)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check NinjaView alert messages and send test orders.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("lint", help="check an alert message")
    pl.add_argument("message", help="the alert message JSON, or - to read it from stdin")

    ps = sub.add_parser("send", help="send a test order to NinjaView, skipping TradingView")
    ps.add_argument("action", nargs="?", choices=["buy", "sell", "close"], help="market buy / market sell / market close")
    ps.add_argument("--url", default=os.environ.get("NINJAVIEW_URL"), help="NinjaView webhook URL (or $NINJAVIEW_URL); http://127.0.0.1:5001 for the local add-on")
    ps.add_argument("--account", default="Sim101", help="NinjaTrader account Name (default Sim101)")
    ps.add_argument("--instrument", help='NinjaTrader instrument, e.g. "MNQ 12-26"')
    ps.add_argument("--qty", type=int, default=1)
    ps.add_argument("--message", help="send this exact JSON instead of building one")
    ps.add_argument("--live", action="store_true", help="allow non-Sim accounts (real orders)")
    ps.add_argument("--force", action="store_true", help="send even if lint finds problems")
    ps.add_argument("--dry-run", action="store_true", help="check and print the message, don't send")
    ps.add_argument("--timeout", type=float, default=10.0)

    args = p.parse_args(argv)

    if args.cmd == "lint":
        message = sys.stdin.read() if args.message == "-" else args.message
        print("Checking message:")
        return 0 if print_findings(lint(message.strip())) else 1

    if args.message:
        message = args.message.strip()
    else:
        if not args.action or not args.instrument:
            p.error("send needs an action (buy/sell/close) and --instrument, or --message")
        message = build_message(args.action, args.account, args.instrument, args.qty)

    print(f"Message: {message}")
    findings = lint(message)
    ok = print_findings(findings)
    if not ok and not args.force:
        print("Not sent: fix the problems above (or pass --force).")
        return 1
    try:
        accounts = [a.strip() for a in json.loads(message).get("account", "").split(",")]
    except (json.JSONDecodeError, AttributeError):
        accounts = []
    live = [a for a in accounts if a and not a.lower().startswith("sim")]
    if live and not args.live:
        print(f"Not sent: {', '.join(live)} is not a Sim account. Pass --live to send a real order.")
        return 1
    if args.dry_run:
        print("Dry run: not sent.")
        return 0
    if not args.url:
        p.error("send needs --url (or set NINJAVIEW_URL)")
    print(f"Sending to {redact(args.url)} ...")
    return send(args.url, message, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
