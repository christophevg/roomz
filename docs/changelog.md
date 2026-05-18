# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
| 0.1.2 | 2026-05-18 | Display names, mobile UX fixes |
| 0.1.1 | 2026-05-15 | Package restructuring |
| 0.1.0 | 2024-05-15 | Initial release |