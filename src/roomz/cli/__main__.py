"""
CLI entry point for running as a module.

Usage:
  python -m roomz.cli [--server URL]
"""

import argparse


def main() -> None:
  parser = argparse.ArgumentParser(description="Roomz Chat CLI")
  parser.add_argument(
    "--server",
    "-s",
    default="http://localhost:8000",
    help="Server URL (default: http://localhost:8000)",
  )
  args = parser.parse_args()

  from .app_tui import run_tui

  run_tui(server_url=args.server)


if __name__ == "__main__":
  main()
