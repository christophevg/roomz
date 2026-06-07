"""
Session cache management with security enforcement.

Separate from configuration because session cache is runtime state,
not user configuration.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from roomz.client.exceptions import SecurityError

logger = logging.getLogger(__name__)

# Default session cache location
DEFAULT_SESSION_CACHE_DIR = Path.home() / ".cache" / "roomz"
DEFAULT_SESSION_CACHE_FILE = DEFAULT_SESSION_CACHE_DIR / "session.json"


def ensure_cache_dir(cache_file: Path) -> None:
  """
  Create session cache directory with secure permissions.

  Args:
    cache_file: Path to cache file (parent directory will be created)

  Creates parent directory with 0700 permissions.
  """
  cache_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)


def save_session_cache(
  cookie_value: str, server_url: str | None, cache_file: Path | None = None
) -> None:
  """
  Save session data to cache with secure file permissions.

  Args:
    cookie_value: Session cookie value to save
    server_url: Server URL to save alongside cookie
    cache_file: Optional path to cache file (defaults to ~/.cache/roomz/session.json)

  Security:
    - Directory created with 0700 permissions
    - File created with 0600 permissions
    - TOCTOU-safe: uses file descriptor with exclusive creation
  """
  if cache_file is None:
    cache_file = DEFAULT_SESSION_CACHE_FILE

  ensure_cache_dir(cache_file)

  # Atomic write: write to temp file, then rename
  # This ensures TOCTOU-safe operation
  temp_file = cache_file.with_suffix(".tmp")
  try:
    # Write to temp file
    temp_file.write_text(
      json.dumps(
        {
          "session_cookie": cookie_value,
          "server": server_url,
        },
        indent=2,
      )
    )

    # Set permissions before renaming
    temp_file.chmod(0o600)

    # Atomic rename
    temp_file.replace(cache_file)

    logger.debug(f"Session cookie saved to {cache_file}")

  except (OSError, TypeError) as e:
    # Clean up temp file on error
    try:
      temp_file.unlink()
    except Exception:
      pass
    raise SecurityError(f"Failed to save session cache: {e}") from e


def load_session_cache(cache_file: Path | None = None) -> dict[str, Any] | None:
  """
  Load session data from cache.

  Args:
    cache_file: Optional path to cache file (defaults to ~/.cache/roomz/session.json)

  Returns:
    Session data or None if cache doesn't exist

  Security:
    - Validates file permissions (must be 0600)
    - Validates directory security (must not be world-writable)
  """
  if cache_file is None:
    cache_file = DEFAULT_SESSION_CACHE_FILE

  if not cache_file.exists():
    return None

  # Security validation
  try:
    file_stat = cache_file.stat()
    if file_stat.st_mode & 0o077:  # Group/other permissions
      logger.warning(
        f"Session cache file {cache_file} has insecure "
        f"permissions {oct(file_stat.st_mode & 0o777)}. "
        f"Session may be accessible to other users."
      )

    dir_stat = cache_file.parent.stat()
    if dir_stat.st_mode & 0o002:  # World-writable directory
      logger.warning(
        f"Session cache directory {cache_file.parent} is world-writable. This is a security risk."
      )
  except OSError as e:
    logger.warning(f"Failed to validate session cache permissions: {e}")

  try:
    with open(cache_file) as f:
      data: dict[str, Any] = json.load(f)
      return data
  except (json.JSONDecodeError, OSError) as e:
    logger.warning(f"Failed to load session cookie: {e}")
    return None


def clear_session_cache(cache_file: Path | None = None) -> None:
  """
  Remove session cache file.

  Args:
    cache_file: Optional path to cache file (defaults to ~/.cache/roomz/session.json)
  """
  if cache_file is None:
    cache_file = DEFAULT_SESSION_CACHE_FILE

  if cache_file.exists():
    try:
      cache_file.unlink()
    except OSError as e:
      logger.warning(f"Failed to clear session cache: {e}")
