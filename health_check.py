#!/usr/bin/env python3
"""Fortnightly health check — verifies the funda + fundainbusiness pipelines
are still finding listings, and posts a summary to Telegram.

Triggered by `fundaland-healthcheck.timer` on the VPS.
"""
from __future__ import annotations

import asyncio
import sqlite3
import subprocess
from datetime import datetime, timezone

import telegram

import config

WINDOW_DAYS = 14
SERVICES = ["fundaland-bot.service", "fundaland-scraper.timer", "xvfb.service"]


def is_active(unit: str) -> bool:
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", unit], stderr=subprocess.DEVNULL
        ).decode().strip()
        return out == "active"
    except subprocess.CalledProcessError:
        return False


def last_scrape_run() -> tuple[str, str]:
    """Return (timestamp, exit_status) of last fundaland-scraper.service activation."""
    try:
        out = subprocess.check_output(
            [
                "systemctl",
                "show",
                "fundaland-scraper.service",
                "--property=ExecMainExitTimestamp",
                "--property=ExecMainStatus",
            ]
        ).decode()
        ts = ""
        status = ""
        for line in out.splitlines():
            if line.startswith("ExecMainExitTimestamp="):
                ts = line.split("=", 1)[1].strip()
            elif line.startswith("ExecMainStatus="):
                status = line.split("=", 1)[1].strip()
        return ts or "(unknown)", status or "?"
    except Exception as e:
        return f"(err: {e})", "?"


def funda_counts(db_path) -> dict:
    """Counts of funda listings overall and within the freshness window."""
    c = sqlite3.connect(str(db_path))
    try:
        total = c.execute(
            "SELECT COUNT(*) FROM listings WHERE source='funda'"
        ).fetchone()[0]
        recent = c.execute(
            f"SELECT COUNT(*) FROM listings "
            f"WHERE source='funda' AND first_seen >= date('now','-{WINDOW_DAYS} days')"
        ).fetchone()[0]
        latest = c.execute(
            "SELECT MAX(first_seen) FROM listings WHERE source='funda'"
        ).fetchone()[0]
        fib_recent = c.execute(
            f"SELECT COUNT(*) FROM listings "
            f"WHERE source='fundainbusiness' AND first_seen >= date('now','-{WINDOW_DAYS} days')"
        ).fetchone()[0]
    finally:
        c.close()
    return {
        "funda_total": total,
        "funda_recent": recent,
        "funda_latest": latest,
        "fib_recent": fib_recent,
    }


def build_report() -> tuple[str, bool]:
    """Return (markdown_message, healthy_flag)."""
    services = {u: is_active(u) for u in SERVICES}
    services_ok = all(services.values())

    last_ts, last_status = last_scrape_run()
    counts = funda_counts(config.DB_PATH)

    # Heuristic: a 14-day window with zero new funda listings in a 50km
    # radius around Amsterdam almost certainly means the selectors drifted.
    drift_suspected = counts["funda_recent"] == 0
    healthy = services_ok and last_status == "0" and not drift_suspected

    icon = "✅" if healthy else "⚠️"
    lines = [f"{icon} <b>FundaLand health check</b>"]
    lines.append(f"\n<b>Services:</b>")
    for unit, ok in services.items():
        mark = "✅" if ok else "❌"
        lines.append(f"  {mark} {unit}")

    lines.append(f"\n<b>Last scraper run:</b> {last_ts} (exit={last_status})")

    lines.append(f"\n<b>Last {WINDOW_DAYS} days:</b>")
    lines.append(f"  \U0001F3E1 funda new: {counts['funda_recent']}")
    lines.append(f"  \U0001F33E fundainbusiness new: {counts['fib_recent']}")
    lines.append(f"\n<b>Funda total in DB:</b> {counts['funda_total']}")
    lines.append(f"<b>Latest funda first_seen:</b> {counts['funda_latest']}")

    if drift_suspected:
        lines.append(
            f"\n⚠️ <b>0 new funda listings in {WINDOW_DAYS} days.</b> "
            "funda.nl selectors may have drifted — inspect funda_scraper.py and re-run dump_funda.py."
        )
    if not services_ok:
        lines.append("\n⚠️ One or more systemd units are not active.")
    if last_status not in ("0", "?"):
        lines.append(f"\n⚠️ Last scraper exit status was {last_status}, not 0.")

    return "\n".join(lines), healthy


async def send(text: str) -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print(text)
        print("\n(Telegram not configured — printed to stdout instead.)")
        return
    bot = telegram.Bot(token=config.TELEGRAM_BOT_TOKEN)
    await bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


def main() -> int:
    text, healthy = build_report()
    asyncio.run(send(text))
    print(f"[{datetime.now(timezone.utc).isoformat()}] healthy={healthy}")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
