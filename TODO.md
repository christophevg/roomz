# TODO

## Bug Fixes

- [x] **B-001: Fix double-quoting of EMAIL_FROM in ResendEmailSender** (2026-05-20)
  - Strip surrounding quotes from `EMAIL_FROM` environment variable
  - Ensure `DEFAULT_FROM_ADDRESS` is used if `EMAIL_FROM` is not set or becomes empty after stripping
  - **Satisfies**: R103
  - **Acceptance**:
    - ✅ `EMAIL_FROM` set with quotes (e.g. '"user@example.com"') sends correctly without double-quotes in JSON
    - ✅ `EMAIL_FROM` set without quotes sends correctly
    - ✅ `EMAIL_FROM` not set uses default

## Backlog

### Iteration 4: JWT Sessions & Private Channels

**Goal**: Stateless authentication with user-owned private channels

- [x] **I4-001: JWT session tokens** (2026-05-15)
  - Replaced in-memory session storage with JWT tokens
  - Added PyJWT dependency
  - Created JWT with claims: sub, email, iat, exp, channel_token, ver
  - Validate JWT on WebSocket connection
  - Check email against ALLOWED_EMAILS env var on every request
  - Token version strategy for session revocation
  - **Delivers**: Stateless sessions, server restart tolerance
  - **Satisfies**: R3, R29, R30, R33, R58, R59, R60, R61
  - **Acceptance**: 
    - ✅ Login with magic link, get JWT
    - ✅ Server restart, reconnect still works
    - ✅ Remove email from ALLOWED_EMAILS, access denied
- [x] **I4-001b: Fix Python client JWT issues** (2026-05-15)
  - Fixed duplicate messages after server reconnection (connection state guard)
  - Fixed auto-reconnection after CLI restart (pass cookie in WebSocket headers)
  - Added `_cached_cookie` for explicit header passing
  - **Delivers**: Reliable Python client authentication

- [x] **I4-002: User-owned private channels** (2026-05-15)
  - Each user gets personal channel: `user:{email}`
  - Channel membership assigned server-side from JWT email claim
  - Web client joins user's channel on connect
  - Python client joins same channel with same JWT
  - Broadcast messages only to user's channel
  - Presence events scoped to user's channel
  - Connection counts in presence events for multi-device awareness
  - **Delivers**: Private chat per user across multiple clients
  - **Satisfies**: R7, R14, R15
  - **Acceptance**:
    - ✅ User A's web and Python clients see each other's messages
    - ✅ User B cannot join User A's channel without valid token
    - ✅ Multiple users have separate, private conversations

**Result**: Users have private channels. JWT enables stateless auth. Server restarts don't force re-login.

---

### Iteration 5: Email Authentication

**Goal**: Production-ready magic link delivery

- [x] **I5-001: Resend email integration** (2026-05-15)
  - Created EmailSender protocol with ConsoleEmailSender and ResendEmailSender
  - Environment-based selection: EMAIL_SENDER=console|resend
  - ConsoleEmailSender logs magic links to server console (development)
  - ResendEmailSender sends HTML emails via Resend API (production)
  - Factory pattern: get_email_sender() returns appropriate implementation
  - Email includes magic link URL and CLI token instructions
  - Fixed circular import by importing email module after server creation
  - Added comprehensive test fixtures for EMAIL_SENDER environment
  - **Delivers**: Real email delivery for magic links
  - **Satisfies**: R1 (complete)
  - **Acceptance**:
    - ✅ Development mode: magic link logged to console
    - ✅ Production mode: Resend sends email
    - ✅ User receives magic link, clicks, authenticates

- [x] **I5-002: Email allow-list** (2026-05-15)
  - ALLOWED_EMAILS env var (comma-separated)
  - Validate email against allow-list on magic link request
  - Validate email against allow-list on JWT verification
  - Clear error message for non-allowed emails
  - **Delivers**: Access control via email allow-list
  - **Satisfies**: Security requirement
  - **Acceptance**:
    - ✅ Only allowed emails can request magic links
    - ✅ Removing email from allow-list revokes access immediately
    - ✅ Non-allowed emails get "not authorized" message

**Result**: Production authentication with Resend. Email allow-list for access control.

---

### Iteration 6: PyPI Publication

**Goal**: Publish roomz to PyPI with comprehensive documentation

- [x] **I6-001: Documentation infrastructure** (2026-05-15)
  - Created docs/ folder with Sphinx configuration (MyST parser, RTD theme)
  - Created .readthedocs.yaml for ReadTheDocs hosting
  - Added docs dependencies to pyproject.toml (sphinx, sphinx-rtd-theme, myst-parser)
  - Created comprehensive documentation pages:
    - index.md - Project overview and quick start
    - installation.md - Installation guide
    - quickstart.md - Step-by-step setup guide
    - api.md - Client library API reference (AsyncClient, SyncClient, CLI)
    - server.md - Server deployment guide with reverse proxy configs
    - configuration.md - Environment variables reference
    - contributing.md - Contribution guidelines
    - changelog.md - Version history
  - Added docs/_build/ to .gitignore
  - **Delivers**: Sphinx documentation site ready for ReadTheDocs
  - **Satisfies**: R-documentation
  - **Acceptance**:
    - ✅ `make html` builds HTML documentation
    - ✅ docs/ includes installation, API reference, configuration
    - ✅ .readthedocs.yaml configured for automatic builds

- [x] **I6-002: Code quality review** (2026-05-15)
  - Reviewed source code for publication readiness
  - All public APIs have docstrings (AsyncClient, SyncClient, etc.)
  - Type hints complete - mypy passes with no errors
  - No debug code or TODO comments found
  - LICENSE file is MIT (correct for open source)
  - Build successful: dist/roomz-0.1.0-py3-none-any.whl
  - **Delivers**: Clean, professional codebase
  - **Satisfies**: R-quality
  - **Acceptance**:
    - ✅ All public functions/classes have docstrings
    - ✅ mypy passes with no errors
    - ✅ ruff passes with no errors
    - ✅ Code review approved

- [x] **I6-003: CI/CD polish** (2026-05-15)
  - Added Coveralls integration to CI workflow
  - Added coverage badge to README
  - Created publish.yml workflow for TestPyPI and PyPI
  - CI runs tests with coverage on all Python versions
  - Coveralls uploads coverage from ubuntu-latest/Python 3.12
  - **Delivers**: Automated quality checks and coverage visibility
  - **Satisfies**: R-ci
  - **Acceptance**:
    - ✅ Coverage badge added to README
    - ✅ publish.yml workflow created for TestPyPI/PyPI
    - ✅ CI pipeline runs tests, lint, typecheck, coverage

- [x] **I6-004: PyPI publication** (2026-05-15)
  - Published to TestPyPI: https://test.pypi.org/project/roomz/0.1.0/
  - Verified installation from TestPyPI
  - Published to PyPI: https://pypi.org/project/roomz/0.1.0/
  - Verified installation from PyPI: `pip install roomz` works
  - **Delivers**: roomz available on PyPI
  - **Satisfies**: R-publication
  - **Acceptance**:
    - ✅ `pip install roomz` works from PyPI
    - ✅ Documentation on ReadTheDocs configured (.readthedocs.yaml)
    - ✅ All entry points work after install

**Result**: roomz published to PyPI with comprehensive documentation, ready for integration into other projects.

---

### Iteration 7: Display Names

**Goal**: Allow users to set custom display names per device/session

- [x] **I7-001: Per-device display names** (2026-05-18)
  - `/name <name>` command to set display name at any time
  - Web client stores in localStorage (or cookie)
  - Python client stores in `~/.roomz/config.toml` or `ROOMZ_DISPLAY_NAME` env var
  - Client sends name to server after connection (same mechanism as `/name`)
  - Server broadcasts display name in presence events
  - Message display: `"{display name} ({email})"` when set, just `email` when not
  - No server storage - fully stateless
  - Standard user input sanitization (no newlines)
  - **Delivers**: Device identification in multi-session scenarios
  - **Satisfies**: R27 (presence includes display name), R35 (session includes preferences)
  - **Acceptance**:
    - ✅ User can set display name via `/name` command
    - ✅ Display name persists across page reloads (web) / restarts (Python)
    - ✅ Messages show `{display name} ({email})` format
    - ✅ Multiple devices for same user can have different names
    - ✅ Unsetting name reverts to email-only display

- [x] **I7-002: Fix "user joined" message styling** (2026-05-18)
  - Current styling has dark text on dark background
  - Update color/styling for better visibility
  - **Delivers**: Visible presence messages
  - **Satisfies**: R68 (mobile-responsive usability)
  - **Acceptance**:
    - ✅ "user joined" messages are clearly visible
    - ✅ Works on both light and dark themes

- [x] **I7-003: Fix mobile title truncation** (2026-05-18)
  - Title "Roomz" truncates to "Ro..." on narrow screens
  - Reduce user dropdown size (replace email with icon-only on mobile)
  - **Delivers**: Full title visibility on mobile
  - **Satisfies**: R68 (mobile-responsive at 320px width)
  - **Acceptance**:
    - ✅ Full title visible on mobile (320px width)
    - ✅ User dropdown uses icon-only on narrow screens

---

### Iteration 8: Mobile Experience

**Goal**: Improve mobile reliability and PWA support

- [ ] **I8-001: PWA support**
  - Enable Progressive Web App support for improved mobile experience
  - Review and improve PWA support in baseweb first, then apply here
  - Add service worker for offline capability
  - Add manifest for installability
  - **Delivers**: Installable PWA with offline support
  - **Satisfies**: R75, R76, R77 (PWA support)
  - **Acceptance**:
    - ✅ App can be installed on mobile home screen
    - ✅ Basic offline functionality works
    - ✅ PWA passes Lighthouse audit


- [ ] **I8-002: Investigate mobile message loss on refresh**
  - Investigate bug: messages disappear when app has been open for a while
  - Determine root cause (WebSocket reconnection? Server restart? Browser behavior?)
  - Document findings for I8-003 solution
  - **Delivers**: Understanding of message loss issue
  - **Acceptance**:
    - ✅ Root cause identified
    - ✅ Solution approach documented

- [ ] **I8-003: Local message caching**
  - Cache room messages in browser storage (localStorage/IndexedDB)
  - Messages need unique IDs for incremental sync
  - On reconnect, inform backend of last known message to receive new messages
  - Note: Full sync requires backend persistence (postponed to 2.0)
  - Initial implementation: frontend caching for immediate display after refresh
  - **Delivers**: Messages persist across app refreshes
  - **Satisfies**: R33 (session persistence), R89 (automatic reconnection)
  - **Acceptance**:
    - ✅ Messages visible immediately after page refresh
    - ✅ Messages cached locally
    - ✅ New messages received after reconnect (when backend persistence available)

---

### Postponed: Developer Experience

- Enable repository as a plugin and create a skill for using/developing clients with the roomz module (cfr ../baseweb)
  - Create Claude Code skill for roomz module usage
  - Document client development patterns
  - **Reason**: Developer experience improvement, not user-facing feature

- Add installable `roomz-skills` script for skill discovery
  - List available skills with descriptions: `roomz-skills`
  - Show full skill content: `roomz-skills <skill name>`
  - If uv/pyproject.toml supports stdout message on install, add message explaining skills are included
  - **Reason**: Experimental feature for agent skill discovery

- Extract magic link sending functionality into standalone PyPI package
  - Reusable in other projects (baseweb/vuetify based and simple Flask/Quart apps)
  - **Reason**: Infrastructure refactoring, not a roomz user feature

---

### Postponed: Observability

- Structured JSON logging
- Request/response logging
- WebSocket connection metrics
- Error rate tracking
- **Reason**: Focus on publication first; observability can be added post-publication

---

## Postponed to 2.0

### Rooms (Named Conversation Spaces)
- Room creation and listing
- Room join/leave
- Named public/private rooms
- **Reason**: User-owned channels cover primary use case

### Plugin System
- Plugin framework
- Presence plugin
- History plugin
- **Reason**: Core features prioritized first

### Persistence
- MongoDB integration
- Message history
- **Reason**: Real-time focus, history not critical for MVP

---

## Done

### Iteration 8: Mobile Experience

**Goal**: Improve mobile reliability and PWA support

- [x] **I8-000: Generalized Configuration Pattern** (Issue #1) (2026-05-26)
  - **Scope**: Create a unified configuration system for ALL client settings
  - **Design Decision**: ✅ Migrate from `~/.roomz/config.toml` (folder) to `~/.roomz.toml` (single file)
    - Simpler user experience (single visible file vs. hidden folder)
    - Better discoverability (standard dotfile pattern)
    - Session cache remains separate at `~/.roomz/session.json` (runtime data, not user config)
  - **API Design**: See `analysis/config-api.md` for complete design document
  - **Configuration Items** (all should follow same pattern):
    - `server_url` (currently mandatory) → becomes optional with config fallback
    - `display_name` (currently `~/.roomz/config.toml`)
    - `session_cache_file` (currently explicit parameter) → default to `~/.roomz/session.json`
  - **Security Review**: See `analysis/config-security.md` for complete security analysis
  - **Priority Order** (finalized):
    1. Explicit parameter (e.g., `AsyncClient(server_url=...)`)
    2. Environment variable (e.g., `ROOMZ_SERVER_URL`, `ROOMZ_DISPLAY_NAME`, `ROOMZ_SESSION_CACHE_FILE`)
    3. `./roomz.toml` in current working directory (project-level config) **⚠️ Requires security validation**
    4. `~/.roomz.toml` in home directory (user-level config)
    5. `~/.roomz/config.toml` (deprecated, backward compatibility with warning)
  - **Security Requirements** (CRITICAL - must implement):
    - **HIGH-1**: Session cache files MUST be created with 0600 permissions (JWT tokens)
    - **HIGH-2**: Current directory config loading MUST validate directory security (reject world-writable)
    - **MEDIUM-1**: Warn if config files have group/other read permissions
    - **MEDIUM-2**: Session cache directory MUST NOT be world-writable
    - **MEDIUM-3**: Validate server URLs (http/https only, no credentials in URL, hostname required)
    - **LOW-1**: Review error messages for information leakage
    - **LOW-2**: Secure migration path for config files (overwrite before deletion)
  - **Implementation Tasks**:
    - [x] Create `src/roomz/client/config.py` module
    - [x] Add `ConfigurationError` exception to `exceptions.py`
    - [x] Add `SecurityError` exception to `exceptions.py`
    - [x] Add file permission enforcement in `_save_session_cookie()`
    - [x] Add directory security validation for config loading
    - [x] Add server URL validation function
    - [x] Add config file permission warnings
    - [x] Update `AsyncClient.__init__()` to use `Config.load()`
    - [x] Update `AsyncClient.connect()` to validate `server_url` (raise ConfigurationError)
    - [x] Update `SyncClient` to delegate to `AsyncClient`
    - [x] Update CLI app to use `Config.load()`
    - [x] Add TOML dependency (`tomli` for Python < 3.11)
    - [x] Add configuration tests (priority chain, backward compat, error messages)
    - [x] Add security tests (permissions, directory validation, URL validation)
    - [x] Update documentation (docs/configuration.md, docs/api.md)
    - [x] Add migration guide to docs
    - [x] Add security documentation to config docs
  - **Backward Compatibility**:
    - Old config location `~/.roomz/config.toml` still works with deprecation warning
    - `server_url: str` parameter signature accepts `None` (non-breaking)
    - CLI `--server` flag becomes optional (uses config if not provided)
  - **Delivers**: Zero-configuration startup, consistent config pattern
  - **Acceptance**:
    - ✅ All config items follow the same priority pattern
    - ✅ `AsyncClient()` works without explicit `server_url` when config exists
    - ✅ `ROOMZ_*` environment variables have highest config priority after explicit parameters
    - ✅ `./roomz.toml` loaded from current directory (with security validation)
    - ✅ `~/.roomz.toml` loaded from home directory
    - ✅ Explicit parameters override all config sources
    - ✅ Clear error messages when required config is missing (actionable guidance)
    - ✅ Migration or compatibility for existing `~/.roomz/config.toml` users
    - ✅ **Security**: Session cache files created with 0600 permissions
    - ✅ **Security**: Warning logged for insecure file/directory permissions
    - ✅ **Security**: Error raised for world-writable directories containing session files
    - ✅ **Security**: Server URLs validated (http/https only, no credentials)
    - ✅ **Security**: Config migration includes secure file handling

- [x] **I8-004: Replace config module with clevis package** (Issue #5) (2026-06-07)
  - Replace custom configuration code (353 lines) with clevis package v0.3.0+
  - **NO SECURITY WRAPPER LAYER NEEDED** - Clevis 0.3.0 has built-in security features
  - Use `clevis.get_config()` with `security` parameter for built-in validation
  - Create `session_cache.py` module for session cache security (0600 permissions)
  - Update TOML format from `[client]` section to top-level (breaking change)
  - Remove `src/roomz/client/config.py` and rewrite using clevis (~60 lines)
  - Update AsyncClient/SyncClient signature: remove `config_path`, add `args`
  - All I8-000 security requirements preserved via Clevis built-in features
  - All existing tests must pass
  - Document new configuration approach in README
  - References: research/clevis-new-release.md, analysis/reporting/I8-004/plan-v2.md
  - **Delivers**: 440+ lines reduction, improved maintainability, standardized config pattern
  - **Satisfies**: Technical debt reduction, improved code quality, I8-000 security requirements
  - **Priority**: P2
  - **Acceptance**:
    - ✅ Custom config module removed (< 70 lines new code)
    - ✅ Session cache files created with 0600 permissions
    - ✅ Clevis security validation active (file permissions, directory security)
    - ✅ All I8-000 security requirements preserved (HIGH-1, HIGH-2, MEDIUM-1, etc.)
    - ✅ AsyncClient/SyncClient use `get_roomz_config(cli=False, args=args)`
    - ✅ TOML format updated to top-level (no `[client]` section)
    - ✅ All existing tests pass
    - ✅ New security tests for permission validation
    - ✅ README updated with new config approach
    - ✅ Migration guide added to changelog
    - ✅ Breaking change documented in changelog

- [x] **I8-005: Deduplicate CLI entry point code** (Issue #3) (2026-06-02)
  - Refactor duplicate CLI entry point code from `__init__.py` and `__main__.py`
  - Create separate `cli` module (not in existing options A/B/C)
  - Call from script definition and `__main__.py`
  - Clean up `__init__.py`
  - **Owner-specified approach**: Create `src/roomz/cli/cli.py` module with shared CLI logic
  - **Satisfies**: Technical debt reduction, code quality
  - **Priority**: P3 (technical debt/refactoring)
  - **Delivers**: Single source of truth for CLI entry point
  - **Acceptance**:
    - ✅ Create `src/roomz/cli/cli.py` module with shared CLI logic
    - ✅ Update `__main__.py` to import and call the new cli module
    - ✅ Clean up `__init__.py` - remove duplicate code
    - ✅ Update pyproject.toml script definition if needed
    - ✅ All existing tests pass
    - ✅ No functional changes - only code reorganization

### Iteration 3: Python Client

**Goal**: Complete ecosystem with both client channels

- [x] **I3-001: Python client library** (2026-05-15)
  - Created src/roomz/client/ package with AsyncClient and SyncClient
  - AsyncClient with python-socketio for WebSocket communication
  - SyncClient wraps AsyncClient with background thread
  - Event emitter pattern: on('message'), on('authenticated'), on('user_joined'), on('user_left'), on('disconnect'), on('error')
  - Connection state management (DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING)
  - Session caching for automatic reconnection
  - login() method to request magic links
  - connect(session_token) for authentication
  - send() with acknowledgment callback
  - Comprehensive test suite (46 tests)
  - **Delivers**: Programmatic access to chat via Python
  - **Satisfies**: R47, R48, R49, R51
  - **Acceptance**: ✅ Python script can connect, send message, receive messages from web client

- [x] **I3-002: Python client packaging** (2026-05-15)
  - Client library included in roomz package (src/roomz/)
  - pyproject.toml updated with dependencies: python-socketio, aiohttp, textual
  - CLI entry point: roomz-cli command
  - TUI application with Textual for terminal UI
  - README with usage examples for AsyncClient, SyncClient, and CLI
  - **Delivers**: Installable client library with CLI
  - **Satisfies**: R48
  - **Acceptance**: ✅ uv run roomz-cli starts TUI, Python client works programmatically

**Result**: Complete minimal ecosystem. Both web and Python clients working. CLI provides terminal access with session caching.

---

### Iteration 2: Temporary Authentication (Partial)

**Goal**: Basic user identification without full auth infrastructure

- [x] **I2-001: Magic Link Authentication** (2026-05-14)
  - Implemented magic link authentication (simplified from secret dialog)
  - Email-based magic link flow with httpOnly session cookies
  - Rate limiting (5 requests per email per hour)
  - Session management with 30-day expiry
  - WebSocket authentication validates session
  - User email displayed in messages and presence events
  - Frontend: AuthDialog component with focus management, ARIA, timeout
  - Backend: /auth/request-magic-link, /auth/verify, /auth/logout, /auth/me endpoints
  - Security: cryptographically secure tokens, single-use, 15-minute expiry
  - Development mode: magic links logged to console
  - Tests: 90 tests passing (45 skipped - need running server)
  - **Delivers**: Secure passwordless authentication
  - **Satisfies**: R1, R2, R3, R4, R5, R6 (magic link auth)
  - **Acceptance**:
    - ✅ Enter email in AuthDialog, click send magic link
    - ✅ Magic link logged to server console (dev mode)
    - ✅ Click magic link to authenticate
    - ✅ Session cookie set (httpOnly, secure, SameSite=Strict)
    - ✅ User email appears in messages
    - ✅ Rate limiting prevents spam (5 per email per hour)
    - ✅ Logout clears session

**Result**: Users can authenticate via magic link. Their email appears with messages. Session persists across page refreshes.

- [x] **I2-002: Logged link authentication** (2026-05-14)
  - **NOTE**: This task was merged into I2-001 implementation
  - Server already logs magic link to console on request
  - Link contains token that authenticates user
  - User copies link to browser to authenticate
  - Simulates magic link flow without email infrastructure
  - **Delivers**: Testable authentication flow for development
  - **Satisfies**: R1 (partial)
  - **Acceptance**: ✅ Copy logged link to browser, get authenticated

---

### Iteration 1: Minimal Chat Broadcast

**Goal**: Working real-time chat with web client

- [x] **I1-001: Minimal Chat Broadcast** (2026-05-14)
  - Created complete baseweb project with SocketIO support
  - Backend: Quart app with SocketIO broadcast endpoint
  - Frontend: Chat UI page with Vuetify 4 (message display, input, send button)
  - Followed hello-world example pattern (pyproject.toml, app/, pages/)
  - No authentication - open connection
  - No persistence - messages in memory only
  - Complete Python package setup (uv-based)
  - **Delivers**: Working real-time chat with web client
  - **Satisfies**: R18, R22, R23, R54, R56, R57, R66, R67, R68, R69, R70
  - **Acceptance**:
    - ✅ Open web app, see chat UI with message area and input
    - ✅ Type message, press Enter or click send, see message appear
    - ✅ Open second browser tab, send message in one, see it appear in both
    - ✅ Connection status visible in UI
    - ✅ Works on mobile (responsive layout)

**Result**: Open the web app, type a message, see it appear on all connected browsers. Pure real-time chat, no auth, no persistence, no rooms.

