"""
Email module for Roomz.

Provides email sending abstraction for magic link authentication.
Supports console-based development and Resend API for production.
"""

import os
from typing import Literal

from .console import ConsoleEmailSender
from .protocol import EmailSender
from .resend import ResendEmailSender

__all__ = [
  "EmailSender",
  "ConsoleEmailSender",
  "ResendEmailSender",
  "get_email_sender",
]

EmailSenderType = Literal["console", "resend"]


def get_email_sender() -> EmailSender:
  """
  Get an EmailSender instance based on EMAIL_SENDER environment variable.

  The factory returns the appropriate EmailSender implementation based
  on configuration:

  - "console" (default): Returns ConsoleEmailSender for development
  - "resend": Returns ResendEmailSender for production (requires RESEND_API_KEY)

  Environment Variables:
    EMAIL_SENDER: Sender type ("console" or "resend", default: "console")
    RESEND_API_KEY: Resend API key (required if EMAIL_SENDER=resend)
    EMAIL_FROM: From address for emails (optional, has default)

  Returns:
    EmailSender instance (ConsoleEmailSender or ResendEmailSender)

  Raises:
    ValueError: If EMAIL_SENDER is invalid or resend is requested without API key

  Example:
    # Development (default)
    sender = get_email_sender()  # ConsoleEmailSender

    # Production
    os.environ["EMAIL_SENDER"] = "resend"
    os.environ["RESEND_API_KEY"] = "re_xxx"
    sender = get_email_sender()  # ResendEmailSender
  """
  # Import inside function to avoid circular import
  from .. import server

  sender_type = os.getenv("EMAIL_SENDER", "console").lower()

  if sender_type == "console":
    server.logger.info(f"Email sender configured: {sender_type} (magic links logged to console)")
    return ConsoleEmailSender()
  elif sender_type == "resend":
    server.logger.info(f"Email sender configured: {sender_type} (sending via Resend API)")
    # ResendEmailSender will validate API key in __init__
    return ResendEmailSender()
  else:
    raise ValueError(
      f"Invalid EMAIL_SENDER '{sender_type}'. Must be 'console' or 'resend'."
    )
