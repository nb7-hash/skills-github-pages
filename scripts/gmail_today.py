#!/usr/bin/env python3
"""
List today's Gmail messages from the INBOX using IMAP.

Environment variables required:
  - GMAIL_USER: your full Gmail address (e.g., user@gmail.com)
  - GMAIL_APP_PASSWORD: your Gmail App Password (required if 2FA is enabled)

Notes:
  - IMAP access must be enabled in your Gmail settings.
  - If you have 2-Step Verification enabled, you must use an App Password.
  - This script lists headers only (From, Subject, Date) and does not download bodies.
"""

import imaplib
import os
import sys
import email
from email.header import decode_header
from datetime import datetime, timedelta, date


IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
INBOX = "INBOX"


def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Missing environment variable: {name}", file=sys.stderr)
    return value or ""


def format_imap_date(d: date) -> str:
    # IMAP expects dates like 08-Oct-2025
    return d.strftime("%d-%b-%Y")


def decode_mime_words(value: str) -> str:
    if not value:
        return ""
    decoded_parts = []
    for part, charset in decode_header(value):
        if isinstance(part, bytes):
            try:
                decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
            except LookupError:
                decoded_parts.append(part.decode("utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


def print_message_summary(index: int, msg: email.message.Message) -> None:
    raw_from = msg.get("From", "")
    raw_subject = msg.get("Subject", "")
    raw_date = msg.get("Date", "")

    from_display = decode_mime_words(raw_from)
    subject_display = decode_mime_words(raw_subject)
    date_display = decode_mime_words(raw_date)

    print(f"{index:3d}. From: {from_display}")
    print(f"     Subject: {subject_display}")
    print(f"     Date: {date_display}")
    print()


def main() -> int:
    user = get_env("GMAIL_USER")
    app_password = get_env("GMAIL_APP_PASSWORD")

    if not user or not app_password:
        print(
            "Set GMAIL_USER and GMAIL_APP_PASSWORD first. Aborting.",
            file=sys.stderr,
        )
        return 1

    # Define today's window: [today 00:00, tomorrow 00:00)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    since_str = format_imap_date(today)
    before_str = format_imap_date(tomorrow)

    try:
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as client:
            client.login(user, app_password)

            typ, _ = client.select(INBOX)
            if typ != "OK":
                print(f"Failed to select mailbox {INBOX}", file=sys.stderr)
                return 2

            # Restrict to today via SINCE and BEFORE window
            search_criteria = (
                "SINCE",
                since_str,
                "BEFORE",
                before_str,
            )
            typ, data = client.search(None, *search_criteria)
            if typ != "OK":
                print("Search failed.", file=sys.stderr)
                return 3

            message_ids = data[0].split() if data and data[0] else []
            if not message_ids:
                print("No messages found for today.")
                return 0

            print(
                f"Found {len(message_ids)} message(s) in {INBOX} for {since_str}.\n"
                "Showing headers only (From, Subject, Date).\n",
            )

            for idx, msg_id in enumerate(message_ids, start=1):
                typ, msg_data = client.fetch(
                    msg_id,
                    "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])",
                )
                if typ != "OK" or not msg_data:
                    print(f"{idx:3d}. <failed to fetch>")
                    print()
                    continue

                # msg_data is a list like [(b'ID (... {bytes}', b'raw header bytes'), b')']
                header_bytes = b""
                for part in msg_data:
                    if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray)):
                        header_bytes += part[1]

                message = email.message_from_bytes(header_bytes)
                print_message_summary(idx, message)

            client.logout()
            return 0
    except imaplib.IMAP4.error as e:
        print(f"IMAP error: {e}", file=sys.stderr)
        return 10
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 11


if __name__ == "__main__":
    sys.exit(main())

