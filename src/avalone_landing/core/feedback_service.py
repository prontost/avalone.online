"""Feedback service for the Avalone portal."""

from __future__ import annotations

from typing import Any

from avalone_core.database import Service

from avalone_landing.config import Settings, settings
from avalone_landing.core.feedback_repository import FeedbackRepository
from avalone_landing.core.mail_service import MailService


class FeedbackService(Service):
    """Business logic for collecting and notifying about user feedback."""

    def __init__(
        self,
        repository: FeedbackRepository | None = None,
        mail_service: MailService | None = None,
        cfg: Settings | None = None,
    ) -> None:
        self._repo = repository or FeedbackRepository()
        self._mail = mail_service or MailService(cfg=cfg)
        self._cfg = cfg or settings()

    def submit(
        self,
        user_id: int | None,
        source_page: str,
        contact: str,
        message: str,
    ) -> int:
        feedback_id = self._repo.create(user_id, source_page, contact, message)
        self._notify_admins(message, contact, source_page)
        return feedback_id

    def list_recent(self, limit: int = 200) -> list[dict[str, Any]]:
        return self._repo.list_recent(limit)

    def _notify_admins(self, message: str, contact: str, source_page: str) -> None:
        recipients = [e.strip() for e in self._cfg.admin_email.split(",") if "@" in e.strip()]
        if not recipients:
            return
        subject = "[Avalone] Новое сообщение авторам"
        body_lines = ["Получено новое сообщение через форму обратной связи.", ""]
        if contact:
            body_lines.append(f"Контакт: {contact}")
        body_lines.append(f"Источник: {source_page or 'неизвестен'}")
        body_lines.append("")
        body_lines.append("Сообщение:")
        body_lines.append(message)
        body_lines.append("")
        body_lines.append(f"Ответить удобнее всего через админку: {self._cfg.web_base_url}/admin/feedback")
        body = "\n".join(body_lines)
        for recipient in recipients:
            try:
                self._mail.send_email(recipient, subject, body)
            except Exception:
                pass
