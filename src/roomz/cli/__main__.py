"""
CLI entry point for running as a module.

Usage:
  python -m roomz.cli [--server URL]
"""

import argparse

from roomz.client.config import Config


def main() -> None:
  parser = argparse.ArgumentParser(description="Roomz Chat CLI")
  parser.add_argument(
    "--server",
    "-s",
    default=None,
    help="Server URL (default: auto-discover from env/config)",
  )
  args = parser.parse_args()

  from .app_tui import run_tui

  if args.server:
    run_tui(config=Config(server_url=args.server))
  else:
    run_tui()


if __name__ == "__main__":
  main()
