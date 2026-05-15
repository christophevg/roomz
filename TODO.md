# TODO

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
