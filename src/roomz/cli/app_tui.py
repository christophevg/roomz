"""
Example TUI chat client demonstrating the Roomz Python client library.

This example shows how to:
1. Create and configure an AsyncClient
2. Register event handlers for real-time updates
3. Connect with or without session caching
4. Send messages and handle responses
5. Manage the connection lifecycle

Basic usage:
    client = AsyncClient(config=Config(server_url="http://localhost:8000"))
    client.on("message", handle_message)
    await client.login("user@example.com")  # Request magic link
    await client.connect(token="magic-link-token")  # Connect
    result = await client.send("Hello!")
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static, TextArea

from roomz.client import AsyncClient
from roomz.client.config import RoomzConfig, get_roomz_config

# =============================================================================
# UI Components (implementation details)
# =============================================================================


class MessageWidget(Static):
  """A single message in the chat (UI widget)."""

  def __init__(
    self,
    email: str,
    content: str,
    timestamp: str,
    is_system: bool = False,
    is_error: bool = False,
    is_success: bool = False,
    current_user: str | None = None,
    display_name: str | None = None,
  ):
    self.email = email
    self.timestamp = timestamp
    self.is_system = is_system
    self.is_error = is_error
    self.is_success = is_success
    self.current_user = current_user
    self.display_name = display_name
    super().__init__(content)

  def _format_timestamp(self, iso_timestamp: str) -> str:
    """Format ISO timestamp to readable time."""
    if not iso_timestamp:
      return datetime.now().strftime("%H:%M:%S")

    try:
      dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
      return dt.strftime("%H:%M:%S")
    except (ValueError, AttributeError):
      return datetime.now().strftime("%H:%M:%S")

  def _format_user_display(self) -> str:
    """Format user display name and email."""
    if self.display_name and self.display_name.strip():
      return f"{self.display_name.strip()} ({self.email})"
    return self.email

  def render(self) -> str:
    ts = self._format_timestamp(self.timestamp)

    if self.is_system:
      return f"[dim italic]{self.content}[/dim italic]"
    elif self.is_error:
      return f"[red]✗[/red] {self.content}"
    elif self.is_success:
      return f"[green]✓[/green] {self.content}"
    else:
      # Use different color for own messages vs others
      user_display = self._format_user_display()
      if self.email == self.current_user:
        color = "green"
      else:
        color = "blue"
      return f"[dim]{ts}[/dim] [{color} bold]{user_display}[/{color} bold]: {self.content}"


class ChatInput(TextArea):
  """Custom TextArea that sends on Enter, newlines on Ctrl+Enter."""

  def __init__(self, *args: Any, **kwargs: Any) -> None:
    super().__init__(*args, **kwargs)
    self._chat_app: ChatApp | None = None

  def on_key(self, event: Any) -> None:
    """Handle key events."""
    if event.key == "ctrl+enter":
      event.stop()
      self.insert("\n")
    elif event.key == "enter":
      event.stop()
      event.prevent_default()
      if self._chat_app:
        text = self.text.strip()
        if text:
          self.load_text("")
          asyncio.create_task(self._chat_app.handle_input(text))


# =============================================================================
# Client Usage Example
# =============================================================================


class ChatApp(App[None]):
  """
  Example chat application using the Roomz AsyncClient.

  This demonstrates the typical flow:
  1. Create client with optional session caching
  2. Register event handlers
  3. Login (request magic link)
  4. Connect with token (or use cached session)
  5. Send/receive messages
  6. Logout (disconnect and clear session)
  """

  CSS_PATH = "styles/chat.tcss"
  TITLE = "Roomz Chat"

  messages: reactive[list[MessageWidget]] = reactive(list)

  def __init__(self, config: RoomzConfig | None = None):
    """
    Initialize the chat application.

    Args:
      config: Configuration object. If None, uses clevis to auto-discover from
               environment and config files (./roomz.toml, ~/.roomz.toml)

    Example:
      >>> # Explicit config
      >>> config = Config(server_url="http://localhost:8000")
      >>> app = ChatApp(config=config)

      >>> # Auto-discovery
      >>> app = ChatApp()
    """
    super().__init__()
    self.email: str | None = None

    # Create client instance once
    # Session caching: store session cookie to auto-reconnect
    # Set to None to disable caching
    self.client = AsyncClient(
      config=config,
      session_cache_file=Path.home() / ".roomz" / "session.json",
    )

    # Register all event handlers
    self._setup_client_handlers()

  def compose(self) -> ComposeResult:
    with VerticalScroll(id="messages"):
      pass
    yield ChatInput(id="input")

  def _show_welcome_messages(self) -> None:
    """Display welcome messages."""
    self.add_system_message("Welcome to Roomz Chat!")
    self.add_system_message(
      "Commands: /login <email>, /token <token>, /name <name>, /name, /logout, /quit"
    )
    self.add_system_message("Enter to send, Ctrl+Enter for new line")

  def on_mount(self) -> None:
    self._show_welcome_messages()
    input_widget = self.query_one("#input", ChatInput)
    input_widget._chat_app = self
    input_widget.focus()

    # Automatically try to connect using cached session
    asyncio.create_task(self._connect())

  def _setup_client_handlers(self) -> None:
    """
    Register event handlers for the client.

    This is the core pattern for handling real-time events:
    - 'authenticated': Connection established, user info available
    - 'message': Chat message received
    - 'user_joined': Another user joined
    - 'user_left': Another user left
    - 'disconnect': Connection lost
    - 'error': Error occurred
    """
    self.client.on("authenticated", self._handle_authenticated)
    self.client.on("message", self._handle_message)
    self.client.on("user_joined", self._handle_user_joined)
    self.client.on("user_left", self._handle_user_left)
    self.client.on("disconnect", self._handle_disconnect)
    self.client.on("error", self._handle_error)
    self.client.on("display_name_changed", self._handle_display_name_changed)

  async def _connect(self) -> None:
    """
    Try to connect to the server using cached session.

    If no cached session exists, the connection fails silently and the
    user must authenticate with /login and /token.
    """
    try:
      await self.client.connect()
    except Exception:
      # Failed to connect, user needs to authenticate
      pass

  async def handle_input(self, text: str) -> None:
    """Handle user input (commands and messages)."""
    if text == "/quit":
      self.exit()
      return

    if text == "/logout":
      await self.logout()
      return

    if text.startswith("/login "):
      email = text[7:].strip()
      if email:
        await self.login(email)
      else:
        self.add_error_message("Usage: /login <email>")
      return

    if text.startswith("/token "):
      token = text[7:].strip()
      if token:
        await self.connect_with_token(token)
      else:
        self.add_error_message("Usage: /token <token>")
      return

    if text == "/name":
      # Clear display name
      await self.set_display_name(None)
      return

    if text.startswith("/name "):
      # Set display name
      name = text[6:].strip()
      if name:
        await self.set_display_name(name)
      else:
        self.add_error_message("Usage: /name <display name>")
      return

    if text.startswith("/"):
      self.add_error_message(f"Unknown command: {text}")
      return

    # Send chat message
    if self.client.connected:
      result = await self.client.send(text)
      if "error" in result:
        self.add_error_message(f"Failed to send: {result['error']}")
    else:
      self.add_error_message("Not connected. Use /login <email> then /token <token>")

  def add_message(self, widget: MessageWidget) -> None:
    messages_container = self.query_one("#messages", VerticalScroll)
    messages_container.mount(widget)
    messages_container.scroll_end(animate=False)

  def add_chat_message(
    self, email: str, content: str, timestamp: str, display_name: str | None = None
  ) -> None:
    self.add_message(
      MessageWidget(email, content, timestamp, current_user=self.email, display_name=display_name)
    )

  def add_system_message(self, content: str) -> None:
    self.add_message(MessageWidget("", content, "", is_system=True))

  def add_error_message(self, content: str) -> None:
    self.add_message(MessageWidget("", content, "", is_error=True))

  def add_success_message(self, content: str) -> None:
    self.add_message(MessageWidget("", content, "", is_success=True))

  async def login(self, email: str) -> None:
    """Request a magic link for authentication."""
    try:
      await self.client.login(email)
      self.add_success_message(f"Magic link requested for: {email}")
      self.add_system_message("Check the server console for the magic link URL")
    except Exception as e:
      self.add_error_message(f"Failed to request magic link: {e}")

  async def connect_with_token(self, token: str) -> None:
    """
    Connect using a magic link token.

    This exchanges the token for a session cookie and establishes
    the WebSocket connection. The session cookie is cached for
    automatic reconnection on restart.
    """
    try:
      # Disconnect if already connected
      if self.client.connected:
        await self.client.disconnect()

      self.add_system_message("Connecting to chat...")
      await self.client.connect(session_token=token)

    except Exception as e:
      self.add_error_message(f"Connection failed: {e}")

  async def logout(self) -> None:
    """Logout: disconnect and clear cached session."""
    await self.client.disconnect()
    self.client.clear_cached_session()
    self.email = None

    # Clear message history
    messages_container = self.query_one("#messages", VerticalScroll)
    for child in messages_container.children:
      child.remove()

    self.add_system_message("Logged out successfully")
    self._show_welcome_messages()

  async def set_display_name(self, name: str | None) -> None:
    """Set display name for this connection."""
    if not self.client.connected:
      self.add_error_message("Not connected. Use /login <email> then /token <token>")
      return

    result = await self.client.set_display_name(name)

    if result.get("status") == "ok":
      display_name = result.get("display_name")
      if display_name:
        self.add_success_message(f"Display name set to: {display_name}")
      else:
        self.add_success_message("Display name cleared. Messages will show your email only.")
    else:
      error = result.get("error", "Unknown error")
      self.add_error_message(f"Failed to set display name: {error}")

  # ===========================================================================
  # Event Handlers
  # ===========================================================================

  async def _handle_authenticated(self, data: dict[str, Any]) -> None:
    """Handle successful authentication."""
    user = data.get("user", {})
    self.email = user.get("email", "unknown")
    self.add_success_message(f"Authenticated as: {self.email}")
    self.add_system_message("Type messages and press Enter to send.")

  async def _handle_message(self, data: dict[str, Any]) -> None:
    """Handle incoming chat message."""
    user = data.get("user", {})
    email = user.get("email", "unknown")
    display_name = user.get("display_name")
    content = data.get("content", "")
    timestamp = data.get("timestamp", "")
    self.add_chat_message(email, content, timestamp, display_name=display_name)

  def _format_user_display(self, user: dict[str, Any]) -> str:
    """Format user display name and email."""
    email: str = user.get("email", "unknown")
    display_name: str | None = user.get("display_name")
    if display_name and display_name.strip():
      return f"{display_name.strip()} ({email})"
    return email

  async def _handle_user_joined(self, data: dict[str, Any]) -> None:
    """Handle user joined event."""
    user = data.get("user", {})
    user_display = self._format_user_display(user)
    self.add_system_message(f"{user_display} joined the chat")

  async def _handle_user_left(self, data: dict[str, Any]) -> None:
    """Handle user left event."""
    user = data.get("user", {})
    user_display = self._format_user_display(user)
    self.add_system_message(f"{user_display} left the chat")

  async def _handle_disconnect(self, data: dict[str, Any]) -> None:
    """Handle disconnection."""
    self.add_error_message("Disconnected from server")
    self.client.clear_cached_session()

  async def _handle_error(self, data: dict[str, Any]) -> None:
    """Handle error event."""
    error = data.get("error", "Unknown error")
    code = data.get("code", 0)
    self.add_error_message(f"Error {code}: {error}")
    # Clear session on authentication errors
    if code == 401:
      self.client.clear_cached_session()

  async def _handle_display_name_changed(self, data: dict[str, Any]) -> None:
    """Handle display_name_changed event."""
    user = data.get("user", {})
    user_display = self._format_user_display(user)
    self.add_system_message(f"{user_display} changed their display name")

  async def on_unmount(self) -> None:
    """Cleanup on app exit."""
    await self.client.disconnect()


def run_tui(config: RoomzConfig | None = None, args: list[str] | None = None) -> None:
  """
  Run the TUI chat application.

  Args:
    config: Configuration object. If None, uses clevis to auto-discover from
            environment and config files (./roomz.toml, ~/.roomz.toml)
    args: CLI arguments (optional, for testing)

  Configuration Resolution Order:
    1. CLI arguments (--server-url, --display-name)
    2. Environment variables (ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME)
    3. ./roomz.toml (current directory) with security validation
    4. ~/.roomz.toml (user home directory)
    5. Dataclass defaults

  Example:
    >>> # Explicit config
    >>> config = RoomzConfig(server_url="http://localhost:8000")
    >>> run_tui(config=config)

    >>> # Auto-discovery with CLI args
    >>> run_tui(args=["--server-url", "http://localhost:8000"])

    >>> # Auto-discovery
    >>> run_tui()
  """
  if config is None:
    config = get_roomz_config(cli=True, args=args)

  app = ChatApp(config=config)
  app.run()
