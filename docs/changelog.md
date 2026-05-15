# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
| 0.1.0 | 2024-05-15 | Initial release |