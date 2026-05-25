"""
ResendEmailSender implementation for production.

This module provides a Resend API-based email sender for sending
magic link emails in production environments.
"""

import asyncio
import logging
import os
from typing import Any

import resend

from .utils import extract_token_from_url

logger = logging.getLogger("roomz")

DEFAULT_FROM_ADDRESS = "no-reply@example.com"
DEFAULT_SUBJECT = "Your Magic Link for Roomz"


class ResendEmailSender:
  """
  Email sender that uses Resend API for production.

  This implementation uses the Resend API to send emails. It handles
  errors internally and returns False on failure rather than raising
  exceptions to the caller.

  Attributes:
    _api_key: Resend API key (validated on init)
    _from_address: Email sender address

  Raises:
    ValueError: If RESEND_API_KEY is not set

  Example:
    sender = ResendEmailSender()
    success = await sender.send_magic_link(
      "user@example.com",
      "https://example.com/auth/verify?token=abc123"
    )
  """

  def __init__(self) -> None:
    """
    Initialize ResendEmailSender with API key validation.

    Raises:
      ValueError: If RESEND_API_KEY environment variable is not set
    """
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
      raise ValueError("RESEND_API_KEY environment variable is required for ResendEmailSender")

    # Soft validation: warn if key format looks wrong
    if not api_key.startswith("re_"):
      logger.warning("RESEND_API_KEY does not start with 're_' - this may indicate an invalid key")

    self._api_key = api_key
    self._from_address = (os.getenv("EMAIL_FROM") or "").strip("'\"") or DEFAULT_FROM_ADDRESS

    # Configure resend module
    resend.api_key = self._api_key

    logger.info(f"ResendEmailSender initialized with from_address={self._from_address}")

  def _generate_html_content(self, magic_link_url: str) -> str:
    """
    Generate HTML email content with magic link.

    Args:
      magic_link_url: Full URL for magic link authentication

    Returns:
      HTML string for email body
    """
    # Extract token from URL for CLI usage
    token = extract_token_from_url(magic_link_url)

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 24px;">Welcome to Roomz</h1>
  </div>
  <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
    <p style="font-size: 16px; margin-bottom: 20px;">
      Click the button below to sign in to your account:
    </p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="{magic_link_url}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
        Sign In to Roomz
      </a>
    </div>
    <p style="font-size: 14px; color: #666; margin-top: 20px;">
      Or copy and paste this link into your browser:
    </p>
    <p style="font-size: 12px; color: #999; word-break: break-all; background: #fff; padding: 10px; border-radius: 5px; border: 1px solid #ddd;">
      {magic_link_url}
    </p>

    <div style="background: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
      <p style="font-size: 14px; color: #333; margin: 0 0 10px 0;">
        <strong>Using the CLI client?</strong>
      </p>
      <p style="font-size: 12px; color: #666; margin: 0 0 5px 0;">
        Start the CLI with <code style="background: #fff; padding: 2px 6px; border-radius: 3px;">roomz-cli</code>
      </p>
      <p style="font-size: 12px; color: #666; margin: 0 0 10px 0;">
        Then type <code style="background: #fff; padding: 2px 6px; border-radius: 3px;">/token &lt;token&gt;</code> with this token:
      </p>
      <p style="font-size: 14px; font-family: monospace; background: #fff; padding: 10px; border-radius: 5px; margin: 0; word-break: break-all; border: 1px solid #ddd;">
        /token {token}
      </p>
    </div>

    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
    <p style="font-size: 12px; color: #999;">
      This magic link will expire in 15 minutes. If you didn't request this link, you can safely ignore this email.
    </p>
  </div>
</body>
</html>
"""

  def _send_email_sync(self, email: str, magic_link_url: str) -> dict[str, Any] | None:
    """
    Synchronous email sending via Resend API.

    This method wraps the synchronous resend API call.

    Args:
      email: Recipient email address
      magic_link_url: Full URL for magic link authentication

    Returns:
      Response dict with 'id' on success, None on failure
    """
    try:
      response = resend.Emails.send(
        {
          "from": self._from_address,
          "to": email,
          "subject": DEFAULT_SUBJECT,
          "html": self._generate_html_content(magic_link_url),
        }
      )
      return {"id": response["id"]}
    except Exception as e:
      logger.error(f"Resend API error for {email}: {e}")
      return None

  async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
    """
    Send magic link email via Resend API.

    Uses run_in_executor to run the synchronous Resend API call
    in a thread pool without blocking the async event loop.

    Args:
      email: Recipient email address
      magic_link_url: Full URL for magic link authentication

    Returns:
      True if email was sent successfully, False on failure.
      Never raises exceptions to the caller.
    """
    try:
      # Run synchronous API call in executor
      loop = asyncio.get_running_loop()
      result = await loop.run_in_executor(None, self._send_email_sync, email, magic_link_url)

      if result and "id" in result:
        logger.info(f"Email sent to {email}: {result['id']}")
        return True
      else:
        logger.error(f"Failed to send email to {email}: no message ID returned")
        return False

    except Exception as e:
      # Log error with message
      logger.error(f"Failed to send email to {email}: {e}")
      return False
