"""
CLI entry point for running as a module.

Usage:
  python -m roomz.cli [--server URL]
"""

from .app_tui import run_tui

if __name__ == "__main__":
  run_tui()
