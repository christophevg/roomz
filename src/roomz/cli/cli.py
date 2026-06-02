"""
Shared CLI logic for Roomz Chat CLI.

This module contains the common argument parsing and execution logic
used by both entry points (__init__.py and __main__.py).
"""

import argparse

from roomz.client.config import Config

from .app_tui import run_tui


def main() -> None:
  """Entry point for the CLI script."""
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
