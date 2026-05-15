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

- [ ] **I4-002: User-owned private channels**
  - Each user gets personal channel: `user:{email}`
  - Channel requires matching channel_token from JWT
  - Web client joins user's channel on connect
  - Python client joins same channel with same JWT
  - Broadcast messages only to user's channel
  - Global channel optional (for public chat)
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

- NOTE: Change of plan: we'll use Resend
  - minimal test implemented in resend_email_test.py

- [ ] **I5-001: SendGrid integration**
  - Add SendGrid dependency
  - Create EmailSender abstraction
  - Implement SendGridEmailSender
  - Implement ConsoleEmailSender (development mode)
  - Environment-based selection: EMAIL_SENDER=console|sendgrid
  - Email template for magic link
  - **Delivers**: Real email delivery for magic links
  - **Satisfies**: R1 (complete)
  - **Acceptance**:
    - ✅ Development mode: magic link logged to console
    - ✅ Production mode: SendGrid sends email
    - ✅ User receives magic link, clicks, authenticates

- [ ] **I5-002: Email allow-list**
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

**Result**: Production authentication with SendGrid. Email allow-list for access control.

---

### Iteration 6: Deploy & Polish

**Goal**: Production-ready deployment

- [ ] **I6-001: Docker setup**
  - Dockerfile for server
  - docker-compose.yml for development
  - Environment-based configuration
  - Health check endpoints
  - **Delivers**: One-command deployment
  - **Acceptance**: docker-compose up runs full stack

- [ ] **I6-002: Observability basics**
  - Structured JSON logging
  - Request/response logging
  - WebSocket connection metrics
  - Error rate tracking
  - **Delivers**: Production visibility
  - **Acceptance**: Logs are structured, metrics visible

**Result**: Deployable service with basic observability.

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
