#!/usr/bin/env python3
"""Build a daily activity digest from the Meme Stocks API and send it by email.

Run on the VPS via cron (e.g. daily at 8:00 AM). Uses only the standard library.

Required env vars for email:
  EMAIL_TO       Recipient address
  SMTP_HOST      SMTP server (e.g. smtp.gmail.com)
  SMTP_PORT      Usually 587 for TLS
  SMTP_USER      SMTP username (e.g. your@gmail.com)
  SMTP_PASSWORD App password or account password

Optional:
  BASE_URL       API base URL (default: http://127.0.0.1:8000)
  EMAIL_FROM     From address (default: SMTP_USER)

If EMAIL_TO or SMTP_* are not set, the digest is printed to stdout only.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    base_url = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    digest_lines: list[str] = []
    digest_lines.append("Meme Stocks – daily activity digest")
    digest_lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    digest_lines.append("")

    def fetch(path: str) -> dict | list | None:
        try:
            req = Request(f"{base_url}{path}", headers={"Accept": "application/json"})
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except (HTTPError, URLError, json.JSONDecodeError, OSError) as e:
            digest_lines.append(f"  Error: {path} – {e}")
            return None

    # Job runs (last few)
    for job in ("reddit-collection", "price-collection", "notification-check", "daily-analysis"):
        data = fetch(f"/api/jobs/{job}/runs")
        if isinstance(data, list):
            digest_lines.append(f"Job: {job}")
            for r in data[:3]:
                run_at = r.get("run_at", "")[:19] if r.get("run_at") else "?"
                digest_lines.append(f"  {run_at}")
            digest_lines.append("")
        elif data is None and "Error" not in digest_lines[-1]:
            digest_lines.append(f"Job: {job} – failed to fetch")
            digest_lines.append("")

    # Daily analysis (top 5)
    analysis = fetch("/api/analysis/daily")
    if isinstance(analysis, list):
        digest_lines.append("Daily analysis (top 5)")
        for row in analysis[:5]:
            s = row.get("symbol", "?")
            score = row.get("composite_score")
            trend = row.get("price_trend", "?")
            mentions = row.get("mention_count", 0)
            score_str = f"{score:.2f}" if score is not None else "n/a"
            digest_lines.append(f"  {s}: composite={score_str} trend={trend} mentions={mentions}")
        digest_lines.append("")
    elif analysis is None and (not digest_lines or "Error" not in digest_lines[-1]):
        digest_lines.append("Daily analysis – failed to fetch")
        digest_lines.append("")

    # Unread notifications
    notifs = fetch("/api/notifications")
    if isinstance(notifs, list):
        unread = [n for n in notifs if not n.get("read")]
        digest_lines.append(f"Unread notifications: {len(unread)}")
        for n in unread[:10]:
            digest_lines.append(f"  [{n.get('severity', '?')}] {n.get('stock_symbol', '?')}: {n.get('message', '')[:60]}")
        digest_lines.append("")
    elif notifs is None and (not digest_lines or "Error" not in digest_lines[-1]):
        digest_lines.append("Notifications – failed to fetch")
        digest_lines.append("")

    body = "\n".join(digest_lines)
    email_to = os.environ.get("EMAIL_TO")
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS")

    if email_to and smtp_host and smtp_user and smtp_password:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        port = int(os.environ.get("SMTP_PORT", "587"))
        from_addr = os.environ.get("EMAIL_FROM", smtp_user)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Meme Stocks digest – {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        msg["From"] = from_addr
        msg["To"] = email_to
        msg.attach(MIMEText(body, "plain", "utf-8"))
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, port) as smtp:
                smtp.starttls(context=context)
                smtp.login(smtp_user, smtp_password)
                smtp.sendmail(from_addr, [email_to], msg.as_string())
            print("Digest sent to", email_to, file=sys.stderr)
        except Exception as e:
            print("Failed to send email:", e, file=sys.stderr)
            sys.exit(1)
    else:
        print(body)
        if not email_to:
            print("\n(Set EMAIL_TO, SMTP_HOST, SMTP_USER, SMTP_PASSWORD to send by email.)", file=sys.stderr)


if __name__ == "__main__":
    main()
