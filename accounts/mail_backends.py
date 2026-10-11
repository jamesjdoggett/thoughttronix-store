"""Development console delivery with directly usable verification URLs."""

from email import policy

from django.core.mail import EmailMessage
from django.core.mail.backends.console import EmailBackend


class ConsoleEmailBackend(EmailBackend):
    """Keep local links on one MIME line rather than quoted-printable fragments."""

    def write_message(self, message: EmailMessage) -> None:
        """Use the RFC line limit so Django preserves complete verification URLs."""
        console_policy = policy.default.clone(max_line_length=998)
        rendered = message.message(policy=console_policy).as_bytes()
        self.stream.write(rendered.decode("utf-8"))
        self.stream.write("\n" + "-" * 79 + "\n")
