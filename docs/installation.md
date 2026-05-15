# Installation

## Requirements

- Python 3.10 or higher
- An email provider for magic link delivery (Resend or console for development)

## Installing from PyPI

```bash
pip install roomz
```

## Installing from Source

```bash
git clone https://github.com/christophevg/roomz.git
cd roomz
pip install -e .
```

## Development Installation

For development, install with dev dependencies:

```bash
pip install roomz[dev]
```

This includes:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `ruff` - Linting and formatting
- `mypy` - Type checking
- `tox` - Multi-environment testing

## Documentation Dependencies

To build the documentation locally:

```bash
pip install roomz[docs]
```

This includes:
- `sphinx` - Documentation generator
- `sphinx-rtd-theme` - ReadTheDocs theme
- `myst-parser` - Markdown support for Sphinx

## Dependencies

Roomz requires the following packages (installed automatically):

| Package | Purpose |
|---------|---------|
| `baseweb` | Web framework foundation |
| `quart` | Async Flask-like framework |
| `python-socketio` | WebSocket support |
| `aiohttp` | Async HTTP client |
| `PyJWT` | JWT token handling |
| `resend` | Email delivery service |
| `rich` | Rich terminal output |
| `textual` | Terminal UI for CLI |
| `python-dotenv` | Environment configuration |

## Verifying Installation

```python
import roomz
print(roomz.__version__)  # Should print version number
```

```{note}
The CLI commands `roomz` (server) and `roomz-cli` (client) are installed automatically.