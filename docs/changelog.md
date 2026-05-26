# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-26

### Added

- **Generalized Configuration Pattern**: Unified configuration system for all client settings
  - `Config` dataclass with auto-discovery from multiple sources
  - Resolution order: explicit config → config_path → prefixed env vars → unprefixed env vars → ./roomz.toml → ~/.roomz.toml
  - Environment variable prefix system: `ROOMZ_PREFIX=DEV` → `DEV_ROOMZ_SERVER_URL`
  - TOML config file support with `[client]` section
  - `Config.auto_discover()` returns discovered path for debugging
  - Structured logging for config discovery
  - `ConfigurationError` exception for clear error messages

### Changed

- **Breaking**: `AsyncClient` and `SyncClient` constructors now accept `config: Config` instead of individual `server_url` and `display_name` parameters
  - Old: `AsyncClient(server_url="http://localhost:5000", display_name="Alice")`
  - New: `AsyncClient(config=Config(server_url="http://localhost:5000", display_name="Alice"))`
  - Or use auto-discovery: `AsyncClient()` with `ROOMZ_SERVER_URL` env var or `~/.roomz.toml`

### Fixed

- **Session cache security**: Session files now created with 0600 permissions (atomic creation with `os.open()` + `O_EXCL`)
- **Server URL validation**: URLs validated to be http/https only, no credentials allowed
- **Email sender**: ResendEmailSender now correctly handles quoted `EMAIL_FROM` values

### Security

- Session cache files created with 0600 permissions (JWT tokens protected)
- Config files loaded with explicit error handling (raises `ConfigurationError` on invalid files)
- Server URL validation prevents credential injection

---

## [0.1.2] - 2026-05-18

### Added

- **Per-device display names**: Users can set custom display names per device/session
  - `/name <name>` command to set display name in chat
  - `/name` (no argument) to clear display name
  - Display format: `"{name} ({email})"` or just `email`
  - Web client: persisted in localStorage
  - Python client: `ROOMZ_DISPLAY_NAME` env var or `~/.roomz/config.toml`
  - Stateless server-side storage (per-connection in memory)
  - Input validation: max 50 chars, no newlines/control chars, XSS prevention

### Fixed

- **System message visibility**: Presence messages (user joined/left) now visible on dark themes
  - Changed from `text-medium-emphasis` to `text-primary` class
  - Subtle primary background for better contrast
- **Mobile title truncation**: Title "Roomz" no longer truncates on narrow screens
  - User dropdown shows icon-only on mobile (< 600px)
  - Full text visible on tablet/desktop

### Changed

- Presence events now include `display_name` field
- New `display_name_changed` WebSocket event for multi-device awareness

---

## [0.1.0] - 2024-05-15

### Added

- Initial release
- Magic link authentication with email delivery
- JWT-based session management with httpOnly cookies
- Real-time WebSocket chat using Socket.IO
- User-owned private channels for isolated messaging
- Python client library (AsyncClient and SyncClient)
- CLI interface (roomz-cli) with Textual TUI
- Session caching for automatic reconnection
- Rate limiting for magic link requests
- ALLOWED_EMAILS access control
- Resend email integration
- Comprehensive test suite

### Security

- HS256 JWT signing (algorithm hardcoded)
- Single-use magic links with 15-minute expiration
- Rate limiting (5 requests per email per hour)
- httpOnly, SameSite=Strict cookies
- Server-side ALLOWED_EMAILS validation on every request
- XSS prevention through message sanitization

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 0.2.0 | 2026-05-26 | Configuration pattern, session security fixes |
| 0.1.2 | 2026-05-18 | Display names, mobile UX fixes |
| 0.1.1 | 2026-05-15 | Package restructuring |
| 0.1.0 | 2024-05-15 | Initial release |