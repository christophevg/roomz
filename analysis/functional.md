# Functional Analysis: Roomz

**Project**: Roomz - Real-time Chatroom Web Service
**Status**: Planning Phase
**Date**: 2026-05-13
**Analyst**: Functional Analyst Agent

## Executive Summary

Roomz is a real-time chatroom web service built with Quart (async Flask) providing WebSocket-based communication, a Python client library, web client interface, and extensible plugin architecture. The system enables users to create, join, and participate in chat rooms with session management and resume capabilities.

## 1. Functional Requirements

### 1.1 User Authentication

**FR-1.1.1 Magic Link Authentication**
- Users authenticate via email-based magic link flow
- System sends one-time magic link to user's email address
- Link expires after configurable timeout (default: 15 minutes)
- Token stored in client localStorage for subsequent requests
- Token refresh mechanism for extended sessions

**FR-1.1.2 Session Token Management**
- Generate cryptographically secure tokens
- Token validation on each WebSocket connection
- Token invalidation on explicit logout or expiration
- Rate limiting on magic link requests to prevent abuse

**Acceptance Criteria:**
- User can request magic link from web interface
- Magic link directs to authenticated session
- Invalid or expired links show appropriate error message
- Token persists across browser sessions in localStorage
- Rate limiting prevents > 5 requests per email per hour

### 1.2 Room Management

**FR-1.2.1 Room Creation**
- Users can create new chat rooms
- Room creator becomes room owner/admin
- Room has unique identifier and optional display name
- Room configuration: public/private, max occupants, message retention

**FR-1.2.2 Room Joining**
- Users can join existing rooms
- Room list/browse functionality for public rooms
- Private rooms require invitation or access code
- Users receive current room state on join (participants, recent messages)

**FR-1.2.3 Room Leaving**
- Users can leave rooms explicitly
- Room owners can transfer ownership before leaving
- Automatic cleanup when last user leaves (configurable)

**Acceptance Criteria:**
- Room creation returns unique room ID
- Users can list available public rooms
- Joining room delivers presence update to existing participants
- Leaving room delivers presence update to remaining participants
- Private rooms reject unauthorized join attempts

### 1.3 Real-time Communication

**FR-1.3.1 WebSocket Connection**
- Persistent WebSocket connection per authenticated user
- Automatic reconnection with backoff on disconnect
- Connection state tracking (connecting, connected, reconnecting, disconnected)
- Heartbeat/ping-pong to detect stale connections

**FR-1.3.2 Message Delivery**
- Real-time message delivery to all room participants
- Messages include: sender, timestamp, content, optional metadata
- Message ordering guaranteed within room
- Delivery confirmation (optional, configurable per message)

**FR-1.3.3 Presence Notifications**
- Users receive notifications when others join/leave rooms
- Presence includes: user identifier, join/leave timestamp, optional display name
- Online/offline status tracking per room

**Acceptance Criteria:**
- WebSocket connection established within 2 seconds
- Messages delivered to all connected room participants within 100ms
- Presence updates delivered within 50ms of join/leave
- Connection handles network interruptions gracefully
- Message order preserved in high-throughput scenarios

### 1.4 Session Management

**FR-1.4.1 Session Lifecycle**
- Create new session: `/session/new` endpoint
- End session: `/session/end` endpoint
- Resume session: `/session/resume` endpoint
- Session tracks: rooms joined, unread messages, last active timestamp

**FR-1.4.2 Session Persistence**
- Sessions persist across browser sessions
- User can resume previous session on new device/browser
- Session includes context: room memberships, preferences
- Session cleanup after configurable inactivity period (default: 30 days)

**Acceptance Criteria:**
- New session returns session ID and authentication token
- Ending session invalidates token and clears localStorage
- Resuming session restores room memberships and unread state
- Session cleanup removes data older than retention period
- Multiple concurrent sessions per user supported

### 1.5 Plugin Architecture

**FR-1.5.1 Plugin System**
- Plugin interface with lifecycle hooks: on_init, on_join, on_leave, on_message, on_shutdown
- Plugins receive room context and can modify behavior
- Plugin registration and dependency management
- Plugin configuration per room

**FR-1.5.2 Built-in Plugins**
- **Session Management Plugin**: Track user sessions across connections
- **Message History Plugin**: Persist and retrieve past messages
- **Presence Plugin**: Track online/offline status and last seen

**FR-1.5.3 Plugin Security**
- Plugins run in isolated context
- Plugin permissions model (read-only, read-write)
- Plugin cannot access other plugin's data without explicit permission

**Acceptance Criteria:**
- Plugins can be added to rooms via configuration
- Plugin hooks execute in defined order
- Plugin errors do not crash server
- Plugins can be disabled without room restart
- Plugin state persists across room lifecycle events

### 1.6 Python Client Library

**FR-1.6.1 Event-based API**
- Client emits events: connected, disconnected, message, presence, error
- Client methods: connect, disconnect, join_room, leave_room, send
- Async/await compatible
- Automatic reconnection with configurable backoff

**FR-1.6.2 Connection Management**
- Connection state management
- Heartbeat handling
- Message queuing during reconnection

**Acceptance Criteria:**
- Client connects with valid token
- Events fire within 10ms of occurrence
- Queued messages delivered on reconnection
- Connection survives network interruptions < 30 seconds
- API matches documented interface

### 1.7 Web Client Interface

**FR-1.7.1 User Interface**
- Responsive design (desktop and mobile)
- Room list with unread indicators
- Message display with timestamps and sender identification
- Message input with send button and Enter key support

**FR-1.7.2 Authentication Flow**
- Email input for magic link request
- Magic link verification page
- Session persistence across page refreshes
- Logout functionality

**FR-1.7.3 Room Navigation**
- Create room interface
- Join room interface (public list or code entry)
- Room settings panel
- Member list panel

**Acceptance Criteria:**
- UI loads within 3 seconds on broadband connection
- Works on Chrome, Firefox, Safari, Edge (latest versions)
- Mobile-responsive at 320px width minimum
- Keyboard navigation supported for accessibility
- Screen reader compatible (ARIA labels)

## 2. User Stories

### US-1: User Authentication
**As a** user
**I want to** authenticate via email magic link
**So that** I can access the chat without managing passwords

**Acceptance Criteria:**
- Enter email on login page
- Receive magic link within 60 seconds
- Click link to authenticate
- Remain logged in across sessions

### US-2: Join Chat Room
**As a** user
**I want to** join a chat room
**So that** I can participate in group conversations

**Acceptance Criteria:**
- Browse list of public rooms
- Click room to join
- See existing participants
- Receive historical messages (configurable limit)

### US-3: Send and Receive Messages
**As a** room participant
**I want to** send and receive messages in real-time
**So that** I can communicate with other participants

**Acceptance Criteria:**
- Type message and press Enter or click send
- Message appears immediately in my view
- Message appears in other participants' views within 100ms
- Messages ordered chronologically

### US-4: Resume Previous Session
**As a** returning user
**I want to** resume my previous session
**So that** I don't lose my room memberships and unread status

**Acceptance Criteria:**
- Click "resume session" on login
- See previously joined rooms
- See unread message count per room
- Reconnect to rooms automatically

### US-5: Use Python Client
**As a** developer
**I want to** use a Python client library
**So that** I can integrate chat functionality into my application

**Acceptance Criteria:**
- Install via pip
- Import and instantiate client
- Connect with authentication token
- Send and receive messages programmatically

### US-6: Extend with Plugins
**As a** developer
**I want to** extend chatroom functionality with plugins
**So that** I can add custom behavior without modifying core

**Acceptance Criteria:**
- Create plugin class implementing interface
- Register plugin with room
- Plugin hooks fire on room events
- Access room context within plugin

## 3. Technology Decisions and Rationale

### 3.1 Server Framework: Quart

**Decision**: Use Quart (async Flask) instead of Flask or Flask-SocketIO

**Rationale:**
- **Async Support**: Native async/await for handling concurrent WebSocket connections
- **Flask Compatibility**: Familiar Flask API patterns reduce learning curve
- **Performance**: Better suited for real-time applications than synchronous Flask
- **Ecosystem**: Can use Flask extensions with compatibility layer
- **WebSockets**: Built-in WebSocket support without additional dependencies

**Alternatives Considered:**
- Flask-SocketIO: Requires additional eventlet/gevent dependency
- FastAPI: Less familiar Flask-style API, steeper learning curve
- Django Channels: Overkill for focused chat service, adds Django overhead

### 3.2 ASGI Server: Uvicorn

**Decision**: Use Uvicorn as ASGI server

**Rationale:**
- **Performance**: Fast, lightweight ASGI server
- **WebSocket Support**: Excellent WebSocket handling
- **Development**: Auto-reload support for development
- **Production Ready**: Battle-tested in production environments
- **Simple**: Minimal configuration required

### 3.3 Web Framework: Baseweb with Vuetify

**Decision**: Use baseweb framework with Vuetify 4 for web client

**Rationale:**
- **Rapid Development**: Baseweb provides structure and common patterns
- **Consistent**: Follows established project patterns
- **Vuetify 4**: Modern Vue 3 compatible UI framework
- **Component Library**: Rich set of pre-built components
- **Customizable**: Theming and styling support

### 3.4 Authentication: Magic Link

**Decision**: Email-based magic link authentication

**Rationale:**
- **User Experience**: No passwords to remember
- **Security**: Reduces credential stuffing risks
- **Simplicity**: No password reset flow needed
- **Modern**: Matches modern authentication patterns (Slack, Medium)
- **Email Verification**: Confirms user has access to email

**Trade-offs:**
- Requires email delivery service
- Dependent on email deliverability
- Users must check email to authenticate

### 3.5 Storage: MongoDB

**Decision**: MongoDB as primary data store (CONFIRMED)

**Rationale:**
- **Flexible Schema**: Natural fit for chat messages with variable metadata
- **Document Model**: Messages, rooms, and sessions map well to document structure
- **Performance**: Good read/write performance for real-time chat workloads
- **Standardization**: Consistent with organization's database choice for new projects
- **Scalability**: Built-in sharding for horizontal scaling when needed
- **Rich Querying**: Supports complex queries for message history and room filtering
- **Change Streams**: Native support for real-time data changes (useful for presence)
- **TTL Indexes**: Native support for automatic document expiration (message retention)

**Data Organization:**
- Collections: `users`, `rooms`, `messages`, `sessions`, `room_memberships`
- Embedded documents for frequently accessed related data
- Indexes on frequently queried fields (room_id, user_id, timestamps)
- TTL indexes for automatic cleanup of messages and sessions

**Future Considerations:**
- Redis can be added later for session caching if performance requires it
- MongoDB Atlas or self-hosted MongoDB deployment options

### 3.6 Plugin Architecture: Hook-based System

**Decision**: Hook-based plugin system with defined lifecycle events

**Rationale:**
- **Flexibility**: Plugins can hook into any stage of room lifecycle
- **Isolation**: Plugin errors contained, don't affect core
- **Extensibility**: New hooks can be added without breaking existing plugins
- **Simplicity**: Clear interface for plugin developers
- **Performance**: Hooks only fire if registered

## 4. Architecture Overview

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Clients                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │   Web Client     │  │  Python Client   │  │  API Client  │ │
│  │  (Vuetify/BW)    │  │  (Event-based)   │  │  (Custom)   │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘ │
└───────────┼──────────────────────┼──────────────────┼─────────┘
            │                      │                  │
            │ WebSocket            │ WebSocket        │ HTTP
            │                      │                  │
┌───────────┴──────────────────────┴──────────────────┴─────────┐
│                     Quart WebSocket Server                      │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                    WebSocket Handler                       │ │
│  │  • Connection management                                   │ │
│  │  • Message routing                                        │ │
│  │  • Event dispatching                                      │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────────────┐ │
│  │ Auth Module │  │ Room Manager│  │   Plugin System         │ │
│  │ • Magic link│  │ • CRUD      │  │ • Plugin registry       │ │
│  │ • Token mgmt│  │ • Membership│  │ • Lifecycle hooks       │ │
│  │ • Sessions  │  │ • Routing   │  │ • Built-in plugins     │ │
│  └─────────────┘  └─────────────┘  └────────────────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                  Session Manager                           │ │
│  │  • Session lifecycle (new, end, resume)                    │ │
│  │  • State tracking                                         │ │
│  │  • Persistence                                            │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
            │
            │ Read/Write
            │
┌───────────┴───────────────────────────────────────────────────┐
│                      Data Layer                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    MongoDB Database                        │ │
│  │  Collections:                                               │ │
│  │  • users (user profiles, authentication)                   │ │
│  │  • rooms (room metadata, settings)                         │ │
│  │  • messages (chat message history)                         │ │
│  │  • sessions (user session state)                           │ │
│  │  • room_memberships (user-room associations)               │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    (Optional) Redis Cache                  │ │
│  │  • Session caching for faster lookups                      │ │
│  │  • Real-time presence optimization                         │ │
│  └───────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
            │
            │ Email
            │
┌───────────┴───────────────────────────────────────────────────┐
│                    External Services                            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                Email Delivery Service                     │  │
│  │  • Magic link emails                                      │  │
│  │  • Notification emails (optional)                        │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### 4.2 Component Interactions

#### Authentication Flow
```
User -> Web Client: Enter email
Web Client -> Server: POST /auth/magic-link
Server -> Email Service: Send magic link email
User -> Email: Click magic link
Email -> Web Client: Redirect with token
Web Client -> Server: POST /auth/verify
Server -> Web Client: Return session token + user info
Web Client: Store token in localStorage
Web Client -> Server: WebSocket connect with token
Server: Validate token, establish connection
```

#### Message Flow
```
User A -> Web Client: Type message, press Enter
Web Client -> Server: WebSocket message event
Server -> Room Manager: Route to room
Room Manager -> Plugin System: Trigger on_message hooks
Plugin System: Process message (history, etc.)
Room Manager -> WebSocket Handler: Broadcast to room participants
Server -> User B Web Client: WebSocket message event
Server -> User C Python Client: WebSocket message event
User B Web Client: Display message
User C Python Client: Emit 'message' event
```

#### Session Resume Flow
```
User -> Web Client: Click "Resume Session"
Web Client -> Server: POST /session/resume (with session ID)
Server -> Database: Retrieve session data
Server: Validate session not expired
Server -> Web Client: Return session state (rooms, preferences)
Web Client: Restore UI state (room memberships, unread counts)
Web Client -> Server: WebSocket connect with token
Server -> User: Join previous rooms, receive missed messages
```

### 4.3 Data Models (MongoDB Documents)

#### User Collection
```javascript
{
  "_id": ObjectId,
  "email": "string (unique, indexed)",
  "display_name": "string (optional)",
  "created_at": ISODate,
  "last_active": ISODate
}
```

#### Room Collection
```javascript
{
  "_id": ObjectId,
  "name": "string",
  "owner_id": ObjectId (reference to User),
  "visibility": "string (public|private)",
  "max_occupants": "integer (null = unlimited)",
  "created_at": ISODate,
  "settings": {
    "plugin_configs": {},
    // retention_days: integer (future enhancement - currently uses global default)
  }
}
// Note: Global message retention is 30 days (configurable).
// Per-room retention settings are a future enhancement.
```

#### Message Collection
```javascript
{
  "_id": ObjectId,
  "room_id": ObjectId (indexed),
  "user_id": ObjectId,
  "content": "string",
  "metadata": {},
  "created_at": ISODate (indexed)
}
// Indexes:
//   { room_id: 1, created_at: -1 } for message history queries
//   TTL index on created_at for auto-deletion (default 30 days)
//     db.messages.createIndex(
//       { "created_at": 1 },
//       { expireAfterSeconds: 2592000 }  // 30 days in seconds
//     )
```

#### Session Collection
```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId (indexed),
  "token_hash": "string (indexed)",
  "created_at": ISODate,
  "last_active": ISODate,
  "rooms": [ObjectId],
  "preferences": {}
}
// TTL index on last_active for automatic expiration (default 30 days)
//   db.sessions.createIndex(
//     { "last_active": 1 },
//     { expireAfterSeconds: 2592000 }  // 30 days in seconds
//   )
```

#### RoomMembership Collection
```javascript
{
  "_id": ObjectId,
  "room_id": ObjectId (indexed),
  "user_id": ObjectId (indexed),
  "joined_at": ISODate,
  "last_read": ISODate,
  "role": "string (member|admin|owner)"
}
// Compound index: { room_id: 1, user_id: 1 } unique
```

### 4.4 Tenancy Model

**Architecture**: Single-tenant deployment

**Characteristics:**
- One deployment = one organization/user
- No tenant isolation concerns in data model
- Simpler security model (no cross-tenant access checks)
- Straightforward configuration and deployment

**Data Isolation**: Not applicable (single tenant)

**Future Consideration**: Multi-tenancy can be added later by:
- Adding tenant_id to all collections
- Implementing tenant context middleware
- Adding data isolation queries
- Currently out of scope for initial implementation

## 5. Non-Functional Requirements

### 5.1 Performance
- Message delivery latency < 100ms (p95)
- WebSocket connection establishment < 2 seconds
- Support 10,000 concurrent connections per server instance
- Handle 1,000 messages per second per room

### 5.2 Scalability
- Horizontal scaling via load balancer
- Sticky sessions not required (stateless server design)
- Redis for distributed state
- Database connection pooling

### 5.3 Security
- HTTPS required for all connections
- WebSocket Secure (WSS) required
- Token validation on every WebSocket message
- Rate limiting on all endpoints
- Input sanitization for all user content
- CORS configuration for allowed origins

### 5.4 Reliability
- 99.9% uptime target
- Automatic reconnection on disconnect
- Message queuing during reconnection (configurable timeout)
- Graceful degradation on Redis/database failure
- Health check endpoints

### 5.5 Maintainability
- Comprehensive test coverage (>80%)
- API documentation (OpenAPI/Swagger)
- Plugin API documentation
- Logging with structured output (JSON)
- Metrics collection (Prometheus compatible)

### 5.6 Observability
- Request/response logging
- WebSocket connection metrics
- Message throughput metrics
- Error rate tracking
- Performance profiling endpoints

## 6. Open Questions and Clarifications Needed

### Q1: Storage Backend Decision (RESOLVED)
**Decision**: MongoDB as primary database
**Rationale**: Standardization on MongoDB for new projects, flexible schema for chat data, good performance for read/write operations. Redis can be added later for session caching if performance requirements demand it.

### Q2: Email Service Integration (DEFERRED)
**Status**: Deferred - evaluate during P2-001 implementation
**Context**: Magic link authentication requires email sending
**Options Considered**:
- SendGrid: User has prior experience with this service
- `simple-email-gw`: Existing project that operates on top of email accounts like iCloud
**Impact**: Affects authentication implementation, operational costs
**Decision Point**: Will be decided when starting Phase 2 implementation
**Note**: Task P2-004 (Email service integration) will be updated with the chosen solution

### Q3: Multi-tenancy Requirements (RESOLVED)
**Decision**: Single-tenant architecture
**Rationale**: One deployment serves one organization/user. Simpler architecture with no tenant isolation concerns. This is the standard approach for initial development and reduces complexity significantly.
**Future Consideration**: Multi-tenancy can be added later if needed, but not designed for in initial implementation.

### Q4: Message Retention Policy (RESOLVED)
**Decision**: Auto-delete after N days using MongoDB TTL indexes
**Default**: 30 days (configurable via environment variable)
**Implementation**: TTL index on `created_at` field in messages collection
**Future Enhancement**: Per-room retention settings (currently out of scope)
**Rationale**: Prevents unbounded database growth, aligns with common privacy practices, simplifies implementation

### Q5: Deployment Environment (DEFERRED)
**Status**: Deferred - decide during Phase 11 (Deployment)
**Context**: Cloud provider, container orchestration, scaling requirements
**Options**: AWS, GCP, Azure, self-hosted Kubernetes, Docker Compose
**Recommendation**: Containerized deployment, cloud-agnostic with provider-specific modules
**Note**: Will be decided when preparing for deployment

### Q6: Plugin Security Model (RESOLVED - INITIAL PHASE)
**Decision**: Start with trusted plugins only
**Rationale**: In the initial implementation, only built-in trusted plugins will be supported. No third-party plugin support initially.
**Future Consideration**: If third-party plugins are needed later, add sandboxing/restricted execution environment
**Impact**: Simpler implementation, no security sandboxing needed initially

## 7. Dependencies and Assumptions

### Dependencies
- Python 3.11+ (for async features and performance)
- Quart framework
- Uvicorn ASGI server
- MongoDB (primary database)
- Motor (async MongoDB driver)
- Redis (optional, for session caching if needed)
- Email delivery service
- Vue 3 + Vuetify 4 (for web client)

### Assumptions
- Users have reliable internet connection for WebSocket
- Email delivery within reasonable time (< 60 seconds)
- Single region deployment initially
- Users comfortable with magic link authentication (no password alternative)
- English language interface initially (internationalization future work)

### Risks
- WebSocket connection reliability on mobile networks
- Email deliverability issues affecting authentication
- MongoDB availability (mitigated with replica sets)
- Plugin misbehavior affecting server stability
- Scale testing required before production

## 8. Success Metrics

### Technical Metrics
- Message delivery latency p95 < 100ms
- WebSocket connection success rate > 99%
- API response time p95 < 200ms
- Test coverage > 80%
- Zero critical security vulnerabilities

### User Experience Metrics
- Time to first message < 30 seconds (from landing)
- Magic link delivery < 60 seconds
- Reconnection time < 5 seconds
- Mobile page load < 3 seconds

### Operational Metrics
- Deployment time < 10 minutes
- Rollback time < 5 minutes
- Log searchable within 1 minute
- Alert response time < 5 minutes