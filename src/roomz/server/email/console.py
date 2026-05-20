"""
ConsoleEmailSender implementation for development.

This module provides a console-based email sender that logs magic links
to the console for development purposes.
"""


import logging

logger = logging.getLogger("roomz")


class ConsoleEmailSender:
  """
  Email sender that logs magic links to console.

  This implementation is designed for development mode. It logs formatted
  output containing the magic link URL via the baseweb server logger
  and always returns True (never fails).

  Attributes:
    None - requires no configuration

  Example:
    sender = ConsoleEmailSender()
    success = await sender.send_magic_link(
      "user@example.com",
      "https://example.com/auth/verify?token=abc123"
    )
    # success is always True
  """

  async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
    """
    Log magic link to console for development.

    Args:
      email: Recipient email address
      magic_link_url: Full URL for magic link authentication

    Returns:
      Always returns True (console logging never fails)
    """
    # Import inside method to avoid circular import
    from .utils import extract_token_from_url

    # Extract token from URL for CLI usage
    token = extract_token_from_url(magic_link_url)

    logger.info(
      f"\n{'=' * 60}\n"
      f"MAGIC LINK for {email}\n"
      f"\n"
      f"URL: {magic_link_url}\n"
      f"\n"
      f"CLI: /token {token}\n"
      f"{'=' * 60}\n"
    )
    return True
