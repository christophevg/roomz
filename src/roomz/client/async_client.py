"""
Async Client

Primary async WebSocket client implementation for Roomz.
"""

import asyncio
import json
import logging
import os
import random
from pathlib import Path
from typing import Any

import aiohttp
import socketio  # type: ignore[import-untyped]
from yarl import URL

from roomz.client.config import Config, resolve_config
from roomz.client.events import EventEmitter, EventHandler
from roomz.client.exceptions import AuthenticationError, ConfigurationError, ConnectionError
from roomz.client.state import ConnectionState

logger = logging.getLogger(__name__)


class AsyncClient:
  """
  Async WebSocket client for Roomz real-time chat.

  Configuration is resolved in this order (highest to lowest priority):
    1. Explicit `config` parameter
    2. Explicit `config_path` parameter (load from file)
    3. Prefixed environment variable (e.g., HELLO_ROOMZ_SERVER_URL)
    4. Unprefixed environment variable (e.g., ROOMZ_SERVER_URL)
    5. ./roomz.toml (current directory)
    6. ~/.roomz.toml (user home directory)
    7. Default Config() (empty, raises ConfigurationError on connect)

  Usage with explicit config:
    config = Config(server_url="http://localhost:5000")
    async with AsyncClient(config=config) as client:
      client.on('message', handle_message)
      await client.send("Hello, world!")

  Usage with config file:
    async with AsyncClient(config_path="~/.roomz.toml") as client:
      await client.connect(session_token="magic-link-token")

  Usage with auto-discovery:
    async with AsyncClient() as client:
      await client.connect(session_token="magic-link-token")

  Environment Variables:
    - ROOMZ_SERVER_URL: Server URL
    - ROOMZ_DISPLAY_NAME: Display name
    - ROOMZ_PREFIX: Prefix for env vars (e.g., "DEV" -> "DEV_ROOMZ_SERVER_URL")

  Config File Format (~/.roomz.toml):
    [client]
    server_url = "http://localhost:5000"
    display_name = "Alice"

  Authentication Flow:
    1. Shared aiohttp.ClientSession is used for HTTP and WebSocket
    2. Call /auth/verify?token=xxx to get session cookie
    3. Cookie is automatically passed to WebSocket connection
  """

  def __init__(
    self,
    config: Config | None = None,
    config_path: str | Path | None = None,
    session_token: str = "",
    session_cache_file: str | Path | None = None,
    *,
    reconnect: bool = True,
    reconnect_delay: float = 1.0,
    max_reconnect_attempts: int = 5,
    connection_timeout: float = 10.0,
  ):
    """
    Initialize async client.

    Args:
      config: Configuration object (highest priority, overrides auto-discovery)
      config_path: Path to config file (overrides auto-discovery, merged with auto-discovered)
      session_token: Magic link token for authentication (optional if session_cache_file is set)
      session_cache_file: Path to cache session cookie (None to disable caching)
      reconnect: Enable automatic reconnection (default: True)
      reconnect_delay: Initial delay between reconnection attempts in seconds (default: 1.0)
      max_reconnect_attempts: Maximum reconnection attempts (default: 5)
      connection_timeout: Timeout for connection in seconds (default: 10.0)

    Note:
      session_cache_file is NOT part of Config because it's local state,
      not shared configuration. It's typically ~/.roomz/session.json.

    Example:
      >>> # Explicit config
      >>> config = Config(server_url="http://localhost:5000", display_name="Alice")
      >>> client = AsyncClient(config=config)

      >>> # Config from file
      >>> client = AsyncClient(config_path="~/.roomz.toml")

      >>> # Auto-discovery
      >>> client = AsyncClient()
    """
    # Resolve configuration
    self._config = resolve_config(config=config, config_path=config_path)
    self._session_token = session_token
    self._reconnect = reconnect
    self._reconnect_delay = reconnect_delay
    self._max_reconnect_attempts = max_reconnect_attempts
    self._connection_timeout = connection_timeout
    self._session_cache_file = Path(session_cache_file) if session_cache_file else None
    self._cached_cookie: str | None = None  # Cached JWT cookie for reconnection

    # Extract values from config
    self._display_name = (
      self._config.display_name.strip() if self._config.display_name else None
    )

    self._connection_state = ConnectionState.DISCONNECTED
    self._user: dict[str, Any] | None = None
    self._session: aiohttp.ClientSession | None = None
    self._sio: socketio.AsyncClient | None = None
    self._events: EventEmitter = EventEmitter()
    self._reconnect_attempts = 0

  @property
  def connected(self) -> bool:
    """True if WebSocket is connected and authenticated."""
    return self._connection_state == ConnectionState.CONNECTED

  @property
  def user(self) -> dict[str, Any] | None:
    """Current user info: {'id': str, 'email': str} or None if not authenticated."""
    return self._user

  @property
  def connection_state(self) -> ConnectionState:
    """Current connection state."""
    return self._connection_state

  @property
  def display_name(self) -> str | None:
    """Current display name (loaded from config/env, may be overridden by server)."""
    return self._display_name

  @property
  def server_url(self) -> str | None:
    """WebSocket server URL from configuration."""
    return self._config.server_url

  def on(self, event: str, handler: EventHandler) -> None:
    """
    Register event handler.

    Args:
      event: Event name ('authenticated', 'message', 'user_joined',
              'user_left', 'disconnect', 'error')
      handler: Callback function receiving event data (sync or async)
    """
    self._events.on(event, handler)

  def off(self, event: str, handler: EventHandler | None = None) -> None:
    """
    Unregister event handler.

    Args:
      event: Event name
      handler: Specific handler to remove, or None to remove all handlers for event
    """
    self._events.off(event, handler)

  async def login(self, email: str) -> bool:
    """
    Request a magic link for authentication.

    Args:
      email: User email address

    Returns:
      True if magic link was requested successfully

    Raises:
      ConfigurationError: If server_url is not configured
      ConnectionError: If request fails
    """
    # Validate configuration
    if self._config.server_url is None:
      raise ConfigurationError(
        "server_url is not configured. "
        "Provide config with server_url, set ROOMZ_SERVER_URL, "
        "or create ./roomz.toml or ~/.roomz.toml"
      )

    if not self._session:
      self._session = aiohttp.ClientSession()

    url = f"{self._config.server_url}/auth/request-magic-link"
    try:
      async with self._session.post(url, json={"email": email}) as resp:
        if resp.status == 200:
          return True
        else:
          data = await resp.json()
          raise ConnectionError(
            f"Failed to request magic link: {data.get('detail', 'Unknown error')}"
          )
    except Exception as e:
      raise ConnectionError(f"Failed to request magic link: {e}") from e

  def _save_session_cookie(self, cookie_value: str) -> None:
    """
    Save session cookie to cache file.

    Security:
    - Creates file with 0600 permissions atomically (no race condition)
    - Uses exclusive creation to prevent symlink attacks
    """
    if not self._session_cache_file:
      return

    try:
      # Ensure parent directory exists
      self._session_cache_file.parent.mkdir(parents=True, exist_ok=True)

      # Check if file exists
      if self._session_cache_file.exists():
        # Update existing file securely
        self._update_session_cookie_secure(cookie_value)
      else:
        # Create new file with correct permissions from the start
        # O_CREAT | O_EXCL ensures atomic creation (no race condition)
        # O_TRUNC truncates if file exists (shouldn't happen with O_EXCL)
        fd = os.open(
          str(self._session_cache_file),
          os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_EXCL,
          mode=0o600,
        )
        try:
          with os.fdopen(fd, "w") as f:
            json.dump(
              {"session_cookie": cookie_value, "server": self._config.server_url}, f
            )
        except (OSError, TypeError) as e:
          os.close(fd)
          logger.warning(f"Failed to write session cookie: {e}")
          return

        logger.debug(f"Session cookie saved to {self._session_cache_file}")

    except FileExistsError:
      # File was created by another process, update it
      self._update_session_cookie_secure(cookie_value)
    except OSError as e:
      logger.warning(f"Failed to save session cookie: {e}")

  def _update_session_cookie_secure(self, cookie_value: str) -> None:
    """Update existing session cookie file with secure permissions."""
    if not self._session_cache_file:
      return

    try:
      # Check and fix permissions if needed
      current_mode = self._session_cache_file.stat().st_mode & 0o777
      if current_mode & 0o077:  # Has group/other permissions
        logger.warning(
          f"Session cache file {self._session_cache_file} has insecure "
          f"permissions {oct(current_mode)}. Restricting to 0600."
        )
        self._session_cache_file.chmod(0o600)

      # Atomic write: write to temp file, then rename
      temp_file = self._session_cache_file.with_suffix(".tmp")
      temp_file.write_text(
        json.dumps({"session_cookie": cookie_value, "server": self._config.server_url})
      )
      temp_file.replace(self._session_cache_file)

    except (OSError, TypeError) as e:
      logger.warning(f"Failed to update session cookie: {e}")

  def _load_session_cookie(self) -> str | None:
    """
    Load session cookie from cache file.

    Security:
    - Validates file permissions before loading
    - Warns if file has insecure permissions
    """
    if not self._session_cache_file or not self._session_cache_file.exists():
      return None

    try:
      # Check file permissions
      current_mode = self._session_cache_file.stat().st_mode & 0o777
      if current_mode & 0o077:  # Has group/other permissions
        logger.warning(
          f"Session cache file {self._session_cache_file} has insecure "
          f"permissions {oct(current_mode)}. Session may be accessible to other users."
        )

      with open(self._session_cache_file) as f:
        data = json.load(f)
        # Only use cookie if server matches
        if data.get("server") == self._config.server_url:
          cookie = data.get("session_cookie")
          return str(cookie) if cookie else None

    except (OSError, json.JSONDecodeError) as e:
      logger.warning(f"Failed to load session cookie: {e}")

    return None

  def clear_cached_session(self) -> None:
    """Clear cached session cookie."""
    if self._session_cache_file and self._session_cache_file.exists():
      try:
        self._session_cache_file.unlink()
      except OSError:
        pass

  async def connect(self, session_token: str | None = None) -> None:
    """
    Establish WebSocket connection with authentication.

    Args:
      session_token: Optional magic link token. If not provided, attempts
                     to use cached session cookie for reconnection.

    Raises:
      ConfigurationError: If server_url is not configured
      ConnectionError: If connection fails
      AuthenticationError: If authentication fails
    """
    # Validate configuration
    if self._config.server_url is None:
      raise ConfigurationError(
        "server_url is not configured. "
        "Provide config with server_url, set ROOMZ_SERVER_URL, "
        "or create ./roomz.toml or ~/.roomz.toml"
      )

    # Validate configuration values
    errors = self._config.validate()
    if errors:
      raise ConfigurationError(f"Invalid configuration: {'; '.join(errors)}")

    # Store as non-optional for type checker
    server_url = self._config.server_url

    self._connection_state = ConnectionState.CONNECTING

    try:
      # Create shared aiohttp session for HTTP and WebSocket if not already set
      if not self._session:
        self._session = aiohttp.ClientSession()

      # Use provided token or constructor token
      token = session_token or self._session_token

      # Try to load cached session cookie if no token provided
      if not token:
        cached_cookie = self._load_session_cookie()
        if cached_cookie:
          # Set the cached session cookie in the cookie jar
          self._session.cookie_jar.update_cookies({"session_token": cached_cookie})
          # Also store for explicit header passing if needed
          self._cached_cookie = cached_cookie

      # Verify magic link token if provided (skip for session resumption)
      if token:
        verify_url = f"{server_url}/auth/verify?token={token}"
        async with self._session.get(verify_url) as resp:
          # Server redirects on success, but cookie is set
          # Check that we got a response (even if redirect)
          if resp.status not in (200, 302, 303):
            self._connection_state = ConnectionState.DISCONNECTED
            raise AuthenticationError(f"Authentication failed: server returned {resp.status}")

          # Extract and save session cookie after successful verification
          cookies = self._session.cookie_jar.filter_cookies(URL(server_url))
          session_cookie = cookies.get("session_token")
          if session_cookie:
            self._save_session_cookie(session_cookie.value)
            self._cached_cookie = session_cookie.value

      # Create Socket.IO client with shared session
      self._sio = socketio.AsyncClient(
        http_session=self._session,
        reconnection=False,  # We handle reconnection ourselves
      )

      # Register Socket.IO event handlers
      self._sio.on("connect", self._on_socket_connect)
      self._sio.on("disconnect", self._on_socket_disconnect)
      self._sio.on("authenticated", self._on_authenticated)
      self._sio.on("message", self._on_message)
      self._sio.on("user_joined", self._on_user_joined)
      self._sio.on("user_left", self._on_user_left)
      self._sio.on("display_name_changed", self._on_display_name_changed)

      # Build headers with cookie for WebSocket handshake
      headers = {}
      if hasattr(self, "_cached_cookie") and self._cached_cookie:
        headers["Cookie"] = f"session_token={self._cached_cookie}"

      # Connect to WebSocket
      await self._sio.connect(
        server_url,
        headers=headers if headers else {},
        wait_timeout=self._connection_timeout,
      )

      # Reset reconnect attempts on successful connection
      self._reconnect_attempts = 0

    except socketio.exceptions.ConnectionError as e:
      self._connection_state = ConnectionState.DISCONNECTED
      # Clean up session on failure
      if self._session:
        await self._session.close()
        self._session = None
      raise ConnectionError(f"Failed to connect: {e}") from e
    except Exception as e:
      self._connection_state = ConnectionState.DISCONNECTED
      # Clean up session on failure
      if self._session:
        await self._session.close()
        self._session = None
      raise ConnectionError(f"Connection error: {e}") from e

  async def disconnect(self) -> None:
    """Close WebSocket connection."""
    # Prevent reconnection during explicit disconnect
    self._reconnect = False

    if self._sio and self._sio.connected:
      await self._sio.disconnect()

    if self._session:
      await self._session.close()
      self._session = None

    self._connection_state = ConnectionState.DISCONNECTED
    self._user = None

  async def __aenter__(self) -> "AsyncClient":
    """Async context manager entry. Calls connect()."""
    await self.connect()
    return self

  async def __aexit__(
    self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
  ) -> None:
    """Async context manager exit. Calls disconnect()."""
    await self.disconnect()

  async def send(self, content: str) -> dict[str, Any]:
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
    if not self._sio or not self._sio.connected:
      raise ConnectionError("Not connected")

    # Create a future to receive the acknowledgment
    ack_future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    def ack_callback(response: dict[str, Any]) -> None:
      """Handle acknowledgment from server."""
      if not ack_future.done():
        ack_future.set_result(response)

    try:
      # Emit message with acknowledgment callback
      await self._sio.emit("message", {"content": content}, callback=ack_callback)

      # Wait for acknowledgment
      return await asyncio.wait_for(ack_future, timeout=5.0)
    except asyncio.TimeoutError:
      return {"error": "Message acknowledgment timeout", "code": 408}
    except Exception as e:
      logger.error(f"Error sending message: {e}")
      return {"error": str(e), "code": 500}

  async def set_display_name(self, display_name: str | None) -> dict[str, Any]:
    """
    Set display name for this connection.

    Display names are per-connection and ephemeral - not stored server-side.
    Each device/session can have its own display name.

    Args:
      display_name: Display name to set, or None/empty to clear

    Returns:
      dict with 'status', 'display_name' on success
      dict with 'error', 'code' on failure

    Raises:
      ConnectionError: If not connected
    """
    if not self._sio or not self._sio.connected:
      raise ConnectionError("Not connected")

    # Normalize: empty string becomes None
    if display_name is not None:
      display_name = display_name.strip() or None

    # Create a future to receive the acknowledgment
    ack_future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    def ack_callback(response: dict[str, Any]) -> None:
      """Handle acknowledgment from server."""
      if not ack_future.done():
        ack_future.set_result(response)

    try:
      # Emit set_display_name event with acknowledgment callback
      await self._sio.emit(
        "set_display_name", {"display_name": display_name}, callback=ack_callback
      )

      # Wait for acknowledgment
      result = await asyncio.wait_for(ack_future, timeout=5.0)

      # Update local display name on success
      if result.get("status") == "ok":
        self._display_name = result.get("display_name")

      return result

    except asyncio.TimeoutError:
      return {"error": "Display name acknowledgment timeout", "code": 408}
    except Exception as e:
      logger.error(f"Error setting display name: {e}")
      return {"error": str(e), "code": 500}

  # Socket.IO event handlers

  async def _on_socket_connect(self) -> None:
    """Handle Socket.IO connect event."""
    logger.debug("Socket.IO connected")

  async def _on_socket_disconnect(self) -> None:
    """Handle Socket.IO disconnect event."""
    logger.debug("Socket.IO disconnected")

    # Emit disconnect event
    await self._events.emit("disconnect", {})

    # Attempt reconnection if enabled
    if self._reconnect:
      await self._attempt_reconnection()

  async def _on_authenticated(self, data: dict[str, Any]) -> None:
    """Handle authenticated event from server."""
    logger.info(f"Authenticated as {data.get('user', {}).get('email', 'unknown')}")

    # Store user info
    self._user = data.get("user")

    # Update state
    self._connection_state = ConnectionState.CONNECTED

    # Send display name if configured
    if self._display_name:
      logger.debug(f"Sending display name: {self._display_name}")
      await self.set_display_name(self._display_name)

    # Emit authenticated event
    await self._events.emit("authenticated", data)

  async def _on_message(self, data: dict[str, Any]) -> None:
    """Handle message event from server."""
    # Only process if connected (prevent duplicate events during reconnection)
    if self._connection_state == ConnectionState.CONNECTED:
      await self._events.emit("message", data)

  async def _on_user_joined(self, data: dict[str, Any]) -> None:
    """Handle user_joined event from server."""
    if self._connection_state == ConnectionState.CONNECTED:
      await self._events.emit("user_joined", data)

  async def _on_user_left(self, data: dict[str, Any]) -> None:
    """Handle user_left event from server."""
    if self._connection_state == ConnectionState.CONNECTED:
      await self._events.emit("user_left", data)

  async def _on_display_name_changed(self, data: dict[str, Any]) -> None:
    """Handle display_name_changed event from server."""
    if self._connection_state == ConnectionState.CONNECTED:
      await self._events.emit("display_name_changed", data)

  async def _attempt_reconnection(self) -> None:
    """Attempt to reconnect with exponential backoff."""
    self._connection_state = ConnectionState.RECONNECTING

    # Validate server_url is configured (should be if connect() was called)
    if self._config.server_url is None:
      logger.error("Cannot reconnect: server_url not configured")
      self._connection_state = ConnectionState.DISCONNECTED
      return

    server_url = self._config.server_url

    while self._reconnect and self._reconnect_attempts < self._max_reconnect_attempts:
      self._reconnect_attempts += 1

      # Calculate delay with exponential backoff and jitter
      delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))
      delay = delay + random.uniform(0, 0.5)  # Add jitter

      logger.info(
        f"Reconnection attempt {self._reconnect_attempts}/{self._max_reconnect_attempts} "
        f"in {delay:.1f}s"
      )

      await asyncio.sleep(delay)

      try:
        # Clean up old Socket.IO client (keep the same session!)
        if self._sio:
          try:
            await self._sio.disconnect()
          except Exception:
            pass

        # Create new Socket.IO client with the SAME session (cookie is preserved)
        self._sio = socketio.AsyncClient(
          http_session=self._session,  # Reuse session - cookie is still there
          reconnection=False,
        )

        # Re-register event handlers
        self._sio.on("connect", self._on_socket_connect)
        self._sio.on("disconnect", self._on_socket_disconnect)
        self._sio.on("authenticated", self._on_authenticated)
        self._sio.on("message", self._on_message)
        self._sio.on("user_joined", self._on_user_joined)
        self._sio.on("user_left", self._on_user_left)
        self._sio.on("display_name_changed", self._on_display_name_changed)

        # Build headers with cookie for WebSocket handshake
        headers = {}
        if hasattr(self, "_cached_cookie") and self._cached_cookie:
          headers["Cookie"] = f"session_token={self._cached_cookie}"

        # Connect (session cookie from original auth is still in self._session)
        await self._sio.connect(
          server_url,
          headers=headers if headers else {},
          wait_timeout=self._connection_timeout,
        )

        # Reset reconnect attempts on successful connection
        self._reconnect_attempts = 0
        return

      except Exception as e:
        logger.warning(f"Reconnection attempt failed: {e}")

    # Max attempts exceeded
    self._connection_state = ConnectionState.DISCONNECTED
    await self._events.emit(
      "error",
      {
        "error": "Max reconnection attempts exceeded",
        "code": 503,
      },
    )
