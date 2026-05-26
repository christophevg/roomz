"""
CLI package for the Roomz Python client.

Provides a Textual TUI interface for the chat client.
"""

from .app_tui import run_tui


def main() -> None:
  """Entry point for the CLI script."""
  import argparse

  from roomz.client.config import Config

  parser = argparse.ArgumentParser(description="Roomz Chat CLI")
  parser.add_argument(
    "--server",
    "-s",
    default=None,
    help="Server URL (default: auto-discover from env/config)",
  )
  args = parser.parse_args()

  if args.server:
    run_tui(config=Config(server_url=args.server))
  else:
    run_tui()


__all__ = ["run_tui", "main"]
