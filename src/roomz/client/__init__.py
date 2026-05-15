"""
Roomz Client Module

Provides async and sync WebSocket clients for Roomz real-time chat.
"""

from roomz.client.async_client import AsyncClient
from roomz.client.events import EventHandler
from roomz.client.exceptions import (
  AuthenticationError,
  ClientError,
  ConnectionError,
)
from roomz.client.state import ConnectionState
from roomz.client.sync_client import SyncClient

__all__ = [
  "AsyncClient",
  "SyncClient",
  "ConnectionState",
  "ClientError",
  "ConnectionError",
  "AuthenticationError",
  "EventHandler",
]
