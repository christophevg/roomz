"""
Connection State

Enum for tracking WebSocket connection states.
"""

from enum import Enum


class ConnectionState(Enum):
  """WebSocket connection states."""

  DISCONNECTED = "disconnected"
  """Not connected, no reconnection in progress."""

  CONNECTING = "connecting"
  """Connection attempt in progress."""

  CONNECTED = "connected"
  """Connected and authenticated."""

  RECONNECTING = "reconnecting"
  """Reconnection attempt in progress after disconnect."""
