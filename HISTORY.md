# Roomz Version History

## 0.4.0 (2026-06-07)

### New Features

#### Baseweb-Style CLI Integration

- **New command-line interface** - Unified CLI following Baseweb standards with commands: init, check, config, serve, version
- **Init command** - Create default roomz.toml configuration file with secure permissions
- **Check command** - Validate configuration without running the application
- **Config command** - Display current configuration in table or TOML format
- **Serve command** - Run roomz application with Gunicorn, supporting all configuration overrides
- **Version command** - Display roomz version information
- **Clevis integration** - Full integration with clevis package for configuration management with priority: CLI args > env vars > project TOML > user TOML > defaults
- **StandaloneApplication class** - Custom Gunicorn application wrapper for proper ASGI app loading

### Improvements

- **Better configuration management** - RoomzConfig dataclass with nested ServerConfig, EmailConfig, and JWTConfig sections
- **Introspection-based utilities** - config_to_toml and print_config_table use dataclasses.asdict() to avoid hardcoding field names
- **Helpful error messages** - Improved error messages for import failures and configuration issues

### Bug Fixes

- **Removed unused cli.py module** - Deleted src/roomz/cli/cli.py after functionality was moved to app_tui.py in I8-005
- **Code cleanup** - Removed trailing whitespace from all source files for consistency

## 0.3.1 (2026-06-07)

### Bug Fixes

- **Removed unused cli.py module** - Deleted src/roomz/cli/cli.py after functionality was moved to app_tui.py in I8-005
- **Code cleanup** - Removed trailing whitespace from all source files for consistency

### Improvements

- **Better code organization** - CLI entry point code is now consolidated in app_tui.py with direct script invocation

## 0.2.2 (2026-06-07)

### Bug Fixes

- **Fixed clevis compatibility issue** - Removed 'from __future__ import annotations' from config.py to resolve compatibility issues with clevis package's nested dataclass handling

## 0.2.1 (2026-06-07)

### New Features

#### Clevis Integration (I8-004)

- **Replaced custom config module with clevis package** - Reduced custom code by 353 lines by adopting the clevis package for configuration management
- **Security validation** - Configuration files with insecure permissions (group/world readable/writable) are now rejected
- **RoomzConfig dataclass** - New structured configuration with built-in validation
- **Session file security** - Session cache files now use secure 0600 permissions

### Improvements

- **Code reduction** - Eliminated 440+ lines of custom configuration and session handling code
- **Better error messages** - Clearer error messages for configuration issues
- **Simplified configuration** - Direct use of clevis for configuration discovery and loading

### Note

The configuration file format remains unchanged. Continue using the `[client]` section in your TOML files:

```toml
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
```

This is the correct clevis pattern and is fully backward compatible.

## 0.2.0 (2025-05-26)

### New Features

#### Configuration Discovery System (I8-000)

- **Generalized configuration pattern** - Configuration values are now discovered automatically from multiple sources with clear priority order:
  1. Explicit `config` parameter (highest priority)
  2. Explicit `config_path` parameter
  3. Prefixed environment variables (e.g., `DEV_ROOMZ_SERVER_URL`)
  4. Unprefixed environment variables (e.g., `ROOMZ_SERVER_URL`)
  5. `./roomz.toml` (current directory)
  6. `~/.roomz.toml` (user home directory)
  7. Default values (lowest priority)

- **Config.discover() returns path** - The `Config.discover()` method now returns a tuple `(config, path)` so callers know which config file was discovered, enabling better logging and debugging

- **Environment variable prefixes** - Support for `ROOMZ_PREFIX` environment variable to enable multiple environment configurations (dev, staging, prod)

- **TOML config file support** - Configuration can be stored in `~/.roomz.toml` or `./roomz.toml` files

```toml
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
```

- **Strict error handling** - Configuration errors (missing required values) are now raised explicitly with clear error messages instead of failing silently

### Improvements

- **Modernized project tooling** - Migrated to `uv`-based Python project standard with updated CI workflows, Makefile, and development tooling
- **Enhanced logging** - Configuration discovery now includes debug logging for better troubleshooting

### Bug Fixes

- **Fixed EMAIL_FROM double-quoting** - Resolved issue where `EMAIL_FROM` environment variable was being double-quoted in ResendEmailSender (B-001)
- **CI stability improvements** - Fixed various CI failures related to config pattern and linting
- **Ruff and mypy compliance** - Resolved all lint and type checking failures

## 0.1.2 (2025-05-15)

### New Features

#### Display Names (I7-001)

- **Per-device display names** - Users can set a custom display name that appears in chat messages as "Name (email)"
- **Display name persistence** - Display names are stored per session and can be set/cleared dynamically
- **Environment variable support** - Display name can be set via `ROOMZ_DISPLAY_NAME` environment variable
- **Config file support** - Display name can be configured in `~/.roomz.toml`

#### User Interface Improvements (I7-002, I7-003)

- **Improved system message visibility** - Enhanced visibility of presence messages (join/leave) on dark themes
- **Mobile-responsive user dropdown** - Icon-only user dropdown on mobile devices for better UX

### Bug Fixes

- **Improved presence message styling** - Better contrast and visibility for user presence updates
- **Mobile UI refinements** - Fixed layout issues on mobile devices

## 0.1.1 (2025-05-14)

### Improvements

#### Package Restructuring

- **Namespaced module structure** - Reorganized package to use proper namespaced modules (`src/roomz/`)
- **Updated import paths** - All imports now use the correct namespaced paths

## 0.1.0 (2025-05-13)

### New Features

#### Python Client Library (I3-001)

- **AsyncClient** - Async WebSocket client for real-time chat with automatic reconnection and session caching
- **SyncClient** - Synchronous wrapper for simpler integration scenarios
- **CLI interface** - Textual TUI for command-line access with split-screen interface
- **Event system** - EventEmitter pattern for handling connection, message, presence, and error events
- **Session caching** - Automatic session persistence for reconnection without re-authentication

#### Private Channels (I4-002)

- **User-owned channels** - Each user has a private channel for direct messaging
- **Channel subscription** - Users can subscribe to multiple channels
- **Channel-based messaging** - Messages are broadcast to channel subscribers

#### Email Integration (I6-001)

- **Resend email sender** - Production email delivery via Resend API
- **Console email sender** - Development mode with console-based magic link logging
- **Configurable email provider** - Switch between console and Resend via `EMAIL_SENDER` environment variable

#### Security & Authentication

- **Magic link authentication** - Passwordless login via email magic links
- **JWT session management** - Secure session tokens with httpOnly cookies
- **Email allowlist** - Access control via `ALLOWED_EMAILS` environment variable
- **Rate limiting** - Protection against magic link spam (5 requests per hour per email)
- **Token expiration** - Configurable magic link (15 min) and JWT (30 days) expiration

#### Server Architecture

- **Quart web framework** - Async Flask-compatible web server
- **SocketIO integration** - Real-time bidirectional communication
- **Baseweb framework** - Built on Baseweb for modular component architecture
- **Vue 3 + Vuetify 4 frontend** - Modern reactive UI with Material Design

### Infrastructure

- **PyPI publication** - Package published to PyPI for easy installation
- **CI/CD pipeline** - GitHub Actions for testing, coverage, and deployment
- **Documentation** - Sphinx documentation for ReadTheDocs
- **Test coverage** - Comprehensive test suite with pytest and async support

---

**Note:** Version history is maintained from git tags. For detailed commit history, see the [GitHub repository](https://github.com/christophevg/roomz/commits/main/).