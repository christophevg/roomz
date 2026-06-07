"""
CLI package for the Roomz Python client.

Provides a Textual TUI interface for the chat client.
"""

from .app_tui import run_tui
from .cli import main

__all__ = ["run_tui", "main"]
