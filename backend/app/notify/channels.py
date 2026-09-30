import smtplib
from collections.abc import Callable
from email.message import EmailMessage
from typing import Any

import httpx

from app.notify.render import Message
from app.notify.store import NotifySettings


class NotifyError(RuntimeError):
    pass


class GotifyChannel:
    def __init__(self, url: str, token: str, *, http: httpx.Client | None = None) -> None:
        self.url = url.rstrip("/")
        self.token = token
        self._http = http or httpx.Client(timeout=10.0)

    def ready(self, ns: NotifySettings) -> bool:
        return bool(self.url and self.token)

    def send(self, message: Message, ns: NotifySettings) -> None:
        body: dict[str, Any] = {"title": message.title, "message": message.body, "priority": message.priority}
        if message.url:
            body["extras"] = {"client::notification": {"click": {"url": message.url}}}
        try:
            response = self._http.post(f"{self.url}/message", headers={"X-Gotify-Key": self.token}, json=body)
        except httpx.HTTPError as exc:
            raise NotifyError(f"Gotify unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise NotifyError(f"Gotify rejected the message: HTTP {response.status_code}")


class EmailChannel:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sender: str,
        *,
        smtp_factory: Callable[..., Any] = smtplib.SMTP_SSL,
    ) -> None:
        self.host, self.port, self.user, self.password, self.sender = host, port, user, password, sender
        self._factory = smtp_factory

    def ready(self, ns: NotifySettings) -> bool:
        return bool(self.host and self.sender and ns.email_recipient)

    def send(self, message: Message, ns: NotifySettings) -> None:
        mail = EmailMessage()
        mail["Subject"] = f"[Janus] {message.title}"
        mail["From"] = self.sender
        mail["To"] = ns.email_recipient
        mail.set_content(message.body + (f"\n\n{message.url}" if message.url else ""))
        try:
            with self._factory(self.host, self.port, timeout=15) as smtp:
                if self.user:
                    smtp.login(self.user, self.password)
                smtp.send_message(mail)
        except (OSError, smtplib.SMTPException) as exc:
            raise NotifyError(f"email failed: {exc}") from exc
