# TODO

## Backlog

### Iteration 2: Temporary Authentication

**Goal**: Basic user identification without full auth infrastructure

- [ ] **I2-002: Logged link authentication**
  - Server logs authentication link to console on startup or request
  - Link contains token that authenticates user
  - User copies link to browser to authenticate
  - Simulates magic link flow without email infrastructure
  - **Delivers**: Testable authentication flow for development
  - **Satisfies**: R1 (partial)
  - **Acceptance**: Copy logged link to browser, get authenticated without entering secret

**Result**: Users can "log in" via shared secret or logged link. Their display name appears with messages. Still no persistence, no rooms.

---

### Iteration 3: Python Client

**Goal**: Complete ecosystem with both client channels

- [ ] **I3-001: Python client library**
  - Create src/roomz/client/client.py with Client class
  - Implement connect() with WebSocket connection and auth
  - Implement disconnect() method
  - Implement send(message) method
  - Event emitter pattern: on('message'), on('connected'), on('error')
  - Connection state management
  - **Delivers**: Programmatic access to chat via Python
  - **Satisfies**: R47, R48, R49, R51
  - **Acceptance**: Python script can connect, send message, receive messages from web client

- [ ] **I3-002: Python client packaging**
  - Create pyproject.toml for roomz-client package
  - Configure for PyPI distribution
  - Add usage examples in examples/ directory
  - Basic README for client usage
  - **Delivers**: Installable client library
  - **Satisfies**: R48
  - **Acceptance**: pip install roomz-client succeeds, example script runs and connects

**Result**: Complete minimal ecosystem. Both web and Python clients working. Every future feature developed for both channels.

---

### Iteration 4: Rooms

**Goal**: Multiple conversation spaces

- [ ] **I4-001: Room creation and listing**
  - POST /rooms endpoint to create room
  - GET /rooms endpoint to list public rooms
  - Room model: id, name, owner_id, visibility, max_occupants
  - Web UI: room list component
  - Web UI: room creation form
  - Python client: create_room(), list_rooms() methods
  - **Delivers**: Multiple conversation spaces
  - **Satisfies**: R7, R8, R9, R10, R11, R12, R62, R63
  - **Acceptance**: Create multiple rooms, see them listed, different messages in different rooms

- [ ] **I4-002: Room join/leave**
  - WebSocket message: "join" with room_id
  - WebSocket message: "leave" with room_id
  - Broadcast presence update to room participants
  - Track room membership per connection
  - Only broadcast messages to room members
  - Web UI: join/leave room buttons
  - Python client: join_room(), leave_room() methods
  - **Delivers**: Room-specific messaging with presence
  - **Satisfies**: R14, R15, R26, R27, R28
  - **Acceptance**: Join room A, see presence notification. Send message, only room A members see it. Leave room A, see presence notification.

**Result**: Multiple chat rooms. Users can join different rooms. Messages go to the right room. Presence updates when joining/leaving.

---

### Iteration 5: Real Authentication

**Goal**: Proper magic link authentication

- [ ] **I5-001: Magic link endpoints**
  - POST /auth/magic-link endpoint accepts email
  - Generate cryptographically secure token
  - Store token hash in memory (MongoDB in I7)
  - POST /auth/verify endpoint accepts token
  - Validate token, return session token
  - Rate limiting: 5 requests per email per hour
  - **Delivers**: Real authentication API
  - **Satisfies**: R1, R2, R4, R5, R6
  - **Acceptance**: Request magic link for email, receive token, verify token, get authenticated session

- [ ] **I5-002: Email integration**
  - Integrate email service (SendGrid or simple-email-gw)
  - Create email template for magic link
  - Send magic link email with verification URL
  - Development mode: log link instead of sending
  - **Delivers**: Users receive magic links via email
  - **Satisfies**: R1 (complete)
  - **Acceptance**: Request magic link, receive email, click link, get authenticated

- [ ] **I5-003: Token persistence**
  - Store session token in localStorage (web client)
  - Token management in Python client
  - Validate token on WebSocket connection
  - Token refresh mechanism for extended sessions
  - Logout functionality (token invalidation)
  - **Delivers**: Persistent login across sessions
  - **Satisfies**: R3, R29, R30, R33, R58, R59, R60, R61
  - **Acceptance**: Log in, close browser, reopen, still authenticated. Log out, cannot access protected endpoints.

**Result**: Full magic link authentication. Users authenticate via email. Login persists across sessions.

---

### Iteration 6: Plugin System

**Goal**: Extensible architecture

- [ ] **I6-001: Plugin framework**
  - Create Plugin abstract base class in src/roomz/plugins/base.py
  - Define lifecycle hooks: on_init, on_join, on_leave, on_message, on_shutdown
  - Create PluginManager class
  - Plugin registration: register_plugin(room_id, plugin)
  - Execute hooks in defined order
  - Plugin error isolation (don't crash server)
  - **Delivers**: Extension capability for custom behavior
  - **Satisfies**: R37, R38, R39, R40, R44
  - **Acceptance**: Create simple test plugin, register with room, see hooks fire on events, plugin errors don't crash server

- [ ] **I6-002: Presence plugin**
  - Create PresencePlugin class
  - Track online/offline status in memory (MongoDB in I7)
  - on_join: record user as online in room
  - on_leave: record user as offline in room
  - Provide presence query API: GET /rooms/<room_id>/presence
  - Last seen timestamp per user
  - **Delivers**: Modular presence tracking
  - **Satisfies**: R27, R28, R43
  - **Acceptance**: Join room, query presence API, see yourself as online. Leave room, see yourself as offline with last seen timestamp.

**Result**: Plugin architecture ready for extensions. Presence feature extracted as plugin.

---

### Iteration 7: Persistence Plugin

**Goal**: Optional message history

- [ ] **I7-001: MongoDB integration**
  - Configure MongoDB connection with Motor (async driver)
  - Create database and collections: users, rooms, messages, sessions
  - Create indexes: room_id, user_id, created_at
  - Connection pooling and error handling
  - Health check includes MongoDB status
  - **Delivers**: Database backend for persistence
  - **Satisfies**: Data layer foundation
  - **Acceptance**: MongoDB connection established, indexes created, health check reports MongoDB status

- [ ] **I7-002: History plugin**
  - Create HistoryPlugin class
  - on_message: store message in MongoDB
  - on_join: retrieve recent messages (configurable limit, default 50)
  - Configure plugin per room: enable/disable history
  - Message retention via MongoDB TTL index (default 30 days)
  - Web UI: display message history on room join
  - Python client: receive history on join_room()
  - **Delivers**: Optional message persistence
  - **Satisfies**: R14, R22, R23, R42
  - **Acceptance**: Join room, see last 50 messages. Send message, close browser, reopen, see message in history. After 30 days, messages auto-delete.

**Result**: Persistence is a plugin. Enable/disable per room. Core product remains real-time chat. History survives server restart.

---

### Iteration 8: Production Readiness

**Goal**: Deployable, tested, documented

- [ ] **I8-001: Unit and integration tests**
  - Configure pytest with async support
  - Test fixtures for Quart test client and MongoDB
  - Authentication tests: magic link flow, token validation, rate limiting
  - WebSocket tests: connection, message broadcast, room join/leave
  - Room tests: create, list, join, leave
  - Plugin tests: registration, lifecycle hooks, error isolation
  - Integration tests: end-to-end message flow
  - Coverage reporting (>80% target)
  - **Delivers**: Confidence in stability, regression prevention
  - **Satisfies**: R90
  - **Acceptance**: pytest runs, all tests pass, coverage >80%

- [ ] **I8-002: API documentation**
  - OpenAPI/Swagger specification for HTTP endpoints
  - WebSocket message protocol documentation
  - Plugin development guide
  - Python client usage guide
  - Web client usage guide
  - **Delivers**: Self-service onboarding for developers
  - **Satisfies**: R91, R92
  - **Acceptance**: New developer can understand API from docs alone. Swagger UI available at /docs.

- [ ] **I8-003: Deployment configuration**
  - Dockerfile for server
  - Dockerfile for web client
  - docker-compose.yml for development
  - Environment-based configuration
  - Health check endpoints: /health, /ready
  - Graceful shutdown handling
  - Basic Kubernetes manifest (optional)
  - **Delivers**: One-command deployment
  - **Satisfies**: R89, deployment needs
  - **Acceptance**: docker-compose up runs full stack. Health checks work. Graceful shutdown doesn't drop messages.

- [ ] **I8-004: Observability**
  - Structured JSON logging
  - Request/response logging
  - WebSocket connection metrics: active connections, messages/second
  - Error rate tracking
  - Prometheus metrics endpoint: /metrics
  - **Delivers**: Production visibility
  - **Satisfies**: R93, R94, R95, R96, R97, R98, R99
  - **Acceptance**: Logs are structured JSON. Metrics endpoint returns Prometheus format. Can see connection count, message rate, error rate.

**Result**: Production-ready chatroom service. Deployable, tested, documented, observable.

---

## Done

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