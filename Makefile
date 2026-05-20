# Makefile for Roomz
# Utility targets for common development actions

-include ~/.claude/Makefile

.PHONY: run-env dev-env test test-all lint format typecheck build publish clean all help run

## run-env: Install production dependencies
run-env:
	uv sync

## dev-env: Install with all dependencies (dev, extras)
dev-env:
	uv sync --extra dev

## test: Run tests with pytest
test: dev-env
	uv run pytest -v

## test-all: Run tests with tox (all Python versions)
test-all: dev-env
	uv run tox

## test-cov: Run tests with coverage report
test-cov: dev-env
	uv run pytest --cov=src/roomz --cov-report=term-missing

## lint: Run ruff linting
lint: dev-env
	uv run ruff check src/ tests/

## format: Format code with ruff
format: dev-env
	uv run ruff check --fix src/ tests/

## typecheck: Run mypy type checking
typecheck: dev-env
	uv run mypy src/roomz/server/

## build: Build distribution packages
build: dev-env
	uv build

## publish: Publish to PyPI (requires credentials)
publish: build
	uv run twine upload dist/*

## publish-test: Publish to TestPyPI (requires credentials)
publish-test: build
	uv run twine upload --repository testpypi dist/*

## clean: Clean build artifacts
clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .coverage .mypy_cache .ruff_cache .tox
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

## check: Run format, lint, test, and typecheck
check: dev-env format lint test typecheck

## run: Run the development server
run: run-env
	uv run gunicorn -k uvicorn.workers.UvicornWorker roomz.server:asgi_app -b 127.0.0.1:8081 --reload

## help: Show this help message
help:
	@echo "Available targets:"
	@echo ""
	@sed -n 's/^## //p' $(MAKEFILE_LIST) | column -t -s ':'
