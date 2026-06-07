"""
Sync Client

Synchronous wrapper around AsyncClient with background thread.
"""

import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Any, cast

from roomz.client.async_client import AsyncClient
from roomz.client.config import RoomzConfig
from roomz.client.events import EventHandler
from roomz.client.state import ConnectionState

logger = logging.getLogger(__name__)


class SyncClient:
  """
  Synchronous WebSocket client for Roomz real-time chat.

  Provides a synchronous API wrapping the async implementation.
  Runs async event loop in background thread.

  Configuration is resolved in this order (highest to lowest priority):
    1. Explicit `config` parameter
    2. CLI arguments (if args provided)
    3. Environment variables (ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME)
    4. ./roomz.toml (current directory) with security validation
    5. ~/.roomz.toml (user home directory)
    6. Dataclass defaults (empty)

  Usage with explicit config:
    config = RoomzConfig(server_url="http://localhost:5000")
    with SyncClient(config=config, session_token="token") as client:
      client.on('message', handle_message)
      client.send("Hello, world!")

  Usage with auto-discovery:
    with SyncClient(session_token="token") as client:
      client.connect()
  """

  def __init__(
    self,
    config: RoomzConfig | None = None,
    args: list[str] | None = None,
    session_token: str = "",
    session_cache_file: str | Path | None = None,
    *,
    reconnect: bool = True,
    reconnect_delay: float = 1.0,
    max_reconnect_attempts: int = 5,
    connection_timeout: float = 10.0,
  ):
    """
    Initialize sync client.

    Args:
      config: Configuration object (highest priority, overrides auto-discovery)
      args: CLI arguments to pass to clevis (optional, for testing)
      session_token: Session token for authentication (optional if session_cache_file is set)
      session_cache_file: Path to cache session cookie (None to disable caching)
      reconnect: Enable automatic reconnection (default: True)
      reconnect_delay: Initial delay between reconnection attempts in seconds (default: 1.0)
      max_reconnect_attempts: Maximum reconnection attempts (default: 5)
      connection_timeout: Timeout for connection in seconds (default: 10.0)

    Example:
      >>> # Explicit config
      >>> config = RoomzConfig(server_url="http://localhost:5000", display_name="Alice")
      >>> client = SyncClient(config=config)

      >>> # Auto-discovery
      >>> client = SyncClient()
    """
    self._async_client = AsyncClient(
      config=config,
      args=args,
      session_token=session_token,
      session_cache_file=session_cache_file,
      reconnect=reconnect,
      reconnect_delay=reconnect_delay,
      max_reconnect_attempts=max_reconnect_attempts,
      connection_timeout=connection_timeout,
    )
    self._loop: asyncio.AbstractEventLoop | None = None
    self._thread: threading.Thread | None = None
    self._started = False

  def _run_coroutine(self, coro: Any) -> Any:
    """
    Run coroutine in dedicated event loop.

    Args:
      coro: Coroutine to run

    Returns:
      Result of the coroutine

    Raises:
      RuntimeError: If event loop is not running
    """
    if self._loop is None or not self._loop.is_running():
      raise RuntimeError("Event loop is not running")

    future = asyncio.run_coroutine_threadsafe(coro, self._loop)
    return future.result()

  def _start_loop(self) -> None:
    """Start event loop in background thread."""
    self._loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self._loop)
    self._loop.run_forever()

  @property
  def connected(self) -> bool:
    """True if WebSocket is connected and authenticated."""
    return self._async_client.connected

  @property
  def user(self) -> dict[str, Any] | None:
    """Current user info: {'id': str, 'email': str} or None if not authenticated."""
    return self._async_client.user

  @property
  def connection_state(self) -> ConnectionState:
    """Current connection state."""
    return self._async_client.connection_state

  @property
  def display_name(self) -> str | None:
    """Current display name."""
    return self._async_client.display_name

  @property
  def server_url(self) -> str | None:
    """WebSocket server URL from configuration."""
    return self._async_client.server_url

  def connect(self) -> None:
    """
    Establish WebSocket connection.

    Raises:
      ConnectionError: If connection fails
      AuthenticationError: If authentication fails
    """
    # Start event loop thread if not running
    if not self._started:
      self._thread = threading.Thread(target=self._start_loop, daemon=True)
      self._thread.start()
      self._started = True

      # Wait for loop to start
      while self._loop is None or not self._loop.is_running():
        time.sleep(0.01)

    self._run_coroutine(self._async_client.connect())

  def disconnect(self) -> None:
    """Close WebSocket connection."""
    if self._loop and self._loop.is_running():
      self._run_coroutine(self._async_client.disconnect())

      # Stop event loop
      self._loop.call_soon_threadsafe(self._loop.stop)
      self._started = False

  def __enter__(self) -> "SyncClient":
    """Context manager entry. Calls connect()."""
    self.connect()
    return self

  def __exit__(
    self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
  ) -> None:
    """Context manager exit. Calls disconnect()."""
    self.disconnect()

  def send(self, content: str) -> dict[str, Any]:
    """
    Send a chat message.

    Args:
      content: Message content

    Returns:
      dict with 'status', 'message_id', 'timestamp' on success
      dict with 'error', 'code' on failure

    Raises:
      ConnectionError: If not connected
    """
    return cast(dict[str, Any], self._run_coroutine(self._async_client.send(content)))

  def set_display_name(self, display_name: str | None) -> dict[str, Any]:
    """
    Set display name for this connection.

    Args:
      display_name: Display name to set, or None/empty to clear

    Returns:
      dict with 'status', 'display_name' on success
      dict with 'error', 'code' on failure

    Raises:
      ConnectionError: If not connected
    """
    return cast(
      dict[str, Any], self._run_coroutine(self._async_client.set_display_name(display_name))
    )

  def on(self, event: str, handler: EventHandler) -> None:
    """
    Register event handler.

    Args:
      event: Event name ('authenticated', 'message', 'user_joined',
              'user_left', 'disconnect', 'error')
      handler: Callback function receiving event data (sync or async)
    """
    self._async_client.on(event, handler)

  def off(self, event: str, handler: EventHandler | None = None) -> None:
    """
    Unregister event handler.

    Args:
      event: Event name
      handler: Specific handler to remove, or None to remove all handlers for event
    """
    self._async_client.off(event, handler)
