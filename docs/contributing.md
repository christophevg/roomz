# Contributing

Thank you for your interest in contributing to Roomz!

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Clone and Install

```bash
git clone https://github.com/christophevg/roomz.git
cd roomz
uv sync
```

### Install Dev Dependencies

```bash
uv sync --extra dev
```

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest --cov=app --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_auth.py -v

# Run across Python versions
uv run tox
```

## Code Style

Roomz uses:
- **Ruff** for linting and formatting
- **MyPy** for type checking

```bash
# Format code
uv run ruff format app/ tests/ src/

# Lint code
uv run ruff check app/ tests/ src/

# Type check
uv run mypy app/
```

## Project Structure

```
roomz/
├── app/                    # Server application
│   ├── __init__.py        # Quart app + SocketIO
│   ├── auth.py            # Authentication logic
│   ├── models.py          # Data models
│   ├── email.py           # Email sending
│   ├── components/        # Vue components
│   └── pages/             # Page routes
├── src/roomz/             # Client library
│   ├── __init__.py        # Public exports
│   ├── client/            # Client implementations
│   │   ├── async_client.py
│   │   ├── sync_client.py
│   │   ├── events.py
│   │   └── exceptions.py
│   └── cli/               # CLI application
├── tests/                 # Test suite
├── docs/                  # Documentation
└── pyproject.toml         # Project configuration
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

### PR Guidelines

- Write tests for new features
- Update documentation
- Follow existing code style
- Keep commits atomic and descriptive

## Reporting Issues

Use [GitHub Issues](https://github.com/christophevg/roomz/issues) for:

- Bug reports
- Feature requests
- Security vulnerabilities (see SECURITY.md)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.