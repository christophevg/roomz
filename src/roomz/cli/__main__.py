"""
CLI entry point for running as a module.

Usage:
  python -m roomz.cli [--server URL]
"""

from .cli import main

if __name__ == "__main__":
  main()
