"""
Event Emitter

Simple event emitter for client events.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

# Handler can be sync (returns None) or async (returns coroutine)
EventHandler = Callable[[dict[str, Any]], None | Coroutine[Any, Any, None]]


class EventEmitter:
  """
  Simple event emitter for client events.

  Supports both sync and async event handlers.
  """

  def __init__(self) -> None:
    """Initialize event emitter."""
    self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

  def on(self, event: str, handler: EventHandler) -> None:
    """
    Register handler for event.

    Args:
      event: Event name ('authenticated', 'message', 'user_joined',
              'user_left', 'disconnect', 'error')
      handler: Callback function receiving event data (sync or async)
    """
    self._handlers[event].append(handler)

  def off(self, event: str, handler: EventHandler | None = None) -> None:
    """
    Unregister handler(s) for event.

    Args:
      event: Event name
      handler: Specific handler to remove, or None to remove all handlers for event
    """
    if handler:
      try:
        self._handlers[event].remove(handler)
      except ValueError:
        pass  # Handler not registered
    else:
      self._handlers[event].clear()

  async def emit(self, event: str, data: dict[str, Any]) -> None:
    """
    Emit event to all registered handlers (async).

    Supports both sync and async handlers.

    Args:
      event: Event name
      data: Event data to pass to handlers
    """
    for handler in self._handlers[event]:
      try:
        result = handler(data)
        if asyncio.iscoroutine(result):
          await result
      except Exception as e:
        logger.error(f"Error in {event} handler: {e}")
