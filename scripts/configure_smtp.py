#!/usr/bin/env python3
"""Configure Gmail SMTP from environment and send a test email."""
import os
import sys

# Ensure project packages are importable
sys.path.insert(0, "/Users/lucifer/github-work/avalone.online/src")

from avalone_core.database import Database
from avalone_landing.core.admin_service import AdminService
from avalone_landing.core.mail_service import MailService
from avalone_landing.config import settings as portal_settings


def main() -> int:
    password = os.environ.get("AVALONE_SMTP_PASSWORD", "").replace(" ", "")
    if not password:
        print("error: AVALONE_SMTP_PASSWORD is empty", file=sys.stderr)
        return 1

    cfg = {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_user": "ortuslucifer@gmail.com",
        "smtp_password": password,
        "smtp_use_tls": "true",
        "mail_from": "ortuslucifer@gmail.com",
        "mail_from_name": "Avalone",
    }

    admin = AdminService()
    admin.update_server_settings(cfg)
    print("SMTP settings saved.")

    to = os.environ.get("AVALONE_TEST_EMAIL", "ortuslucifer@gmail.com")
    try:
        admin.send_test_email(to)
        print(f"Test email sent to {to}.")
    except Exception as exc:
        print(f"Failed to send test email: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
