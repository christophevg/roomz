"""
CLI package for the Roomz Python client.

Provides a Textual TUI interface for the chat client.
"""

from .app_tui import run_tui


def main() -> None:
  """Entry point for the CLI script."""
  import argparse

  parser = argparse.ArgumentParser(description="Roomz Chat CLI")
  parser.add_argument(
    "--server",
    "-s",
    default="http://localhost:8000",
    help="Server URL (default: http://localhost:8000)",
  )
  args = parser.parse_args()

  run_tui(server_url=args.server)


__all__ = ["run_tui", "main"]
