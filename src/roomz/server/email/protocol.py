"""
EmailSender Protocol for abstract email sending.

This module defines the EmailSender protocol that all email sender
implementations must conform to.
"""

from typing import Protocol


class EmailSender(Protocol):
  """
  Protocol for email sender implementations.

  Defines the interface for sending magic link emails. Implementations
  must provide an async send_magic_link method that returns bool.

  Returns:
    True if email was sent successfully, False otherwise.

  Note:
    Implementations should handle all errors internally and return
    False rather than raising exceptions to the caller.
  """

  async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
    """
    Send a magic link email to the specified address.

    Args:
      email: Recipient email address
      magic_link_url: Full URL for magic link authentication

    Returns:
      True if email was sent successfully, False on failure.
      Never raises exceptions to the caller.
    """
    ...
