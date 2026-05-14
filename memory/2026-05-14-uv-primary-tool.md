# UV is the Primary Python Project Tool

**Date**: 2026-05-14
**Context**: Roomz I1-001 implementation

## Standard

UV is THE single source of truth for Python project management.

## Commands

All commands MUST use `uv run`:

| Purpose | Command |
|---------|---------|
| Tests | `uv run pytest` |
| Run | `uv run gunicorn -k uvicorn.workers.UvicornWorker app:asgi_app` |
| Format | `uv run black .` |
| Lint | `uv run ruff check .` |
| Python | `uv run python -c "..."` |

## Installation

**Single command is sufficient:**

```bash
uv sync
```

DO NOT give multiple installation commands:
- ❌ `uv sync && uv sync --extra dev && uv pip install -e .`
- ✓ `uv sync`

The `uv sync` command:
- Creates `.venv` if needed
- Installs all dependencies
- Installs dev dependencies (from `[project.optional-dependencies]`)
- Syncs to lock file

## Validation

Before starting work, validate:

```bash
# Check for pyproject.toml
ls pyproject.toml

# Verify uv is installed
uv --version

# Sync dependencies
uv sync

# Verify package imports work
uv run python -c "from app import server"

# Verify tests can collect
uv run pytest --collect-only
```

## Makefile

All projects MUST have Makefile with uv commands:

```makefile
include ~/.claude/Makefile

test:
	uv run pytest

format:
	uv run black .
	uv run ruff format .

lint:
	uv run ruff check .

check: format lint test

run:
	uv run gunicorn -k uvicorn.workers.UvicornWorker app:asgi_app
```

## Common Mistakes

| Mistake | Correct Approach |
|---------|------------------|
| `pytest` | `uv run pytest` |
| `python main.py` | `uv run python main.py` |
| Multiple install commands | Just `uv sync` |
| `pip install -e .` | `uv sync` (handles editable installs) |

## Lessons Learned

From Roomz I1-001 session:
- User had to correct: "use uv-based commands"
- User had to explain: "just uv sync should work"
- Always validate uv setup BEFORE starting implementation
- Check: `uv sync`, `uv run python -c "..."`, `uv run pytest --collect-only`