# I9-002: Participant List Display

**Task ID**: I9-002
**Issue**: #9
**Status**: Analysis Complete
**Date**: 2026-06-07

## Overview

This analysis covers the implementation of a visible participant list showing all users in a room with their active/online status. The feature addresses the need for visibility into who is present in a conversation, which is essential for multi-agent coordination scenarios.

## Requirements from Issue #9

From the GitHub issue:

> A list of (active) participants should be visible in the UI. Active between brackets, because participants can go offline, yet still be part of the room. Indication of active/being online is also useful in this context.

### Primary Requirements

1. **UI Visibility**: Show all participants in the room
2. **Active Status**: Indicate who is currently online/active
3. **Persistence**: Offline participants remain visible (part of room history)
4. **Web Client**: Always visible participant list
5. **Python CLI**: `/who` command to list participants

### Additional Context from Codebase Review

- Current system uses user-owned private channels (`user:{email}`)
- Presence events: `user_joined`, `user_left`, `display_name_changed`
- Each user can have multiple connections (multi-device support)
- Connection counts are tracked: `total_connections`, `remaining_connections`

## Current Architecture

### Server-Side Presence Tracking

**Location**: `src/roomz/server/__init__.py`

```python
# In-memory connection tracking: {sid: {email, user_id, ip, connected_at, display_name, connection_id}}
connected_clients: dict[str, dict[str, Any]] = {}
```

**Current Events**:
- `user_joined`: Broadcast to user's channel when a connection is established
- `user_left`: Broadcast to user's channel when a connection is closed
- `display_name_changed`: Broadcast when a user changes their display name

**Current Limitations**:
- Presence events are scoped to user's private channel only
- No aggregate view of all participants in a room
- No persistent participant list (purely real-time)
- No online/offline status indicator beyond join/leave events

### Channel Model

Current: **User-owned private channels**
- Each user gets: `user:{email}`
- Messages broadcast to user's channel only
- No cross-user visibility (by design for privacy)

**Challenge**: How to show participants across private channels?

## Functional Requirements

### FR1: Participant List Storage

The system must maintain a persistent list of participants who have been in the room.

**Design Options**:

| Approach | Pros | Cons |
|----------|------|------|
| **A. Server-side in-memory registry** | Simple, real-time updates | Lost on server restart |
| **B. Database persistence** | Survives restarts, scalable | Additional infrastructure, complexity |
| **C. Hybrid: in-memory + optional DB** | Best of both, graceful degradation | More complex implementation |

**Recommendation**: Start with **Option A** (in-memory registry) for MVP. Design for future database persistence (Phase 2). This aligns with current architecture (in-memory connection tracking).

### FR2: Participant Data Structure

Each participant entry should contain:

```python
{
  "email": str,                    # Primary identifier
  "user_id": str,                  # Unique user ID
  "display_name": str | None,      # Optional display name
  "first_seen": datetime,          # When they first joined
  "last_active": datetime,         # Last activity timestamp
  "connection_count": int,         # Current active connections (0 = offline)
  "status": str,                   # "active" | "idle" | "offline"
}
```

**Connection Count Semantics**:
- `connection_count > 0`: User has active WebSocket connections
- `connection_count == 0`: User is offline but was previously in room

### FR3: Active Status Determination

**Online/Offline**:
- Online: `connection_count > 0`
- Offline: `connection_count == 0`

**Activity Status** (future enhancement):
- Active: User has sent a message in last 5 minutes
- Idle: Online but no recent activity
- Offline: No active connections

**MVP Scope**: Online/offline only. Activity status deferred to I11-001 (Participant Status with typing indicator).

### FR4: Web Client Participant Panel

**UI Location Options**:

| Location | Pros | Cons |
|----------|------|------|
| **Right sidebar** | Standard pattern, always visible | Takes width, may crowd on mobile |
| **Collapsible left drawer** | Can hide on mobile | Not "always visible" per requirement |
| **Top bar dropdown** | Mobile-friendly | Requires click to view |

**Recommendation**: **Right sidebar** on desktop, **bottom sheet** on mobile.

**Mobile Behavior**:
- Width < 600px: Participant list collapses to icon button
- Click/expand shows participant list as overlay or bottom sheet
- Always accessible with one tap

**Visual Design**:
```
┌──────────────────────────────┬─────────────┐
│                              │ Participants│
│  Chat Messages               │             │
│                              │ ● Alice      │
│  [message]                    │   (active)  │
│                              │             │
│  [message]                    │ ○ Bob        │
│                              │   (offline) │
│                              │             │
│  [input]                     │ ● Charlie    │
│                              │   (active)  │
└──────────────────────────────┴─────────────┘
```

**Status Indicators**:
- Green dot (●): Active/online
- Gray dot (○): Offline
- Display format: `{display_name} ({email})` or just `email`

**Sorting**:
- Active participants first (alphabetically by display name)
- Offline participants second (alphabetically by display name)

### FR5: Python CLI `/who` Command

Add `/who` command to existing CLI command set:

**Current Commands** (from `app_tui.py`):
- `/login <email>` - Request magic link
- `/token <token>` - Connect with token
- `/name <name>` - Set display name
- `/name` - Clear display name
- `/logout` - Disconnect and clear session
- `/quit` - Exit the CLI

**New Command**:
- `/who` - List all participants with status

**Output Format**:
```
Participants (3 online, 2 offline):

Online:
  ● Alice (alice@example.com)
  ● Charlie (charlie@example.com)
  ● Dave (dave@example.com)

Offline:
  ○ Bob (bob@example.com)
  ○ Eve (eve@example.com)
```

### FR6: Real-time Updates

**Events to Handle**:
1. User joins: Add to participant list, increment connection count
2. User leaves: Decrement connection count, update status to offline if 0
3. Display name change: Update name in participant list
4. New participant: Add to list (first-time join)

**Broadcast Events** (new):
- `participant_list_update`: Sent to all users when participant list changes
- Payload: Full participant list or delta update

## Technical Design

### Server-Side Changes

**1. Participant Registry** (`src/roomz/server/__init__.py`)

```python
# In-memory participant registry: {email: ParticipantInfo}
participants: dict[str, dict[str, Any]] = {}

def update_participant(email: str, updates: dict) -> None:
    """Update participant info and broadcast changes."""
    if email not in participants:
        # New participant
        participants[email] = {
            "email": email,
            "user_id": None,
            "display_name": None,
            "first_seen": datetime.now(timezone.utc),
            "last_active": datetime.now(timezone.utc),
            "connection_count": 0,
        }

    participants[email].update(updates)

    # Broadcast update to all users
    await broadcast_participant_list()
```

**2. Connection Tracking Updates**

Modify `on_connect()`:
```python
# After registering connected_clients[sid]
email = client_info.get("email")
update_participant(email, {
    "connection_count": participants.get(email, {}).get("connection_count", 0) + 1,
    "last_active": datetime.now(timezone.utc),
})

# Send full participant list to new connection
await server.socketio.emit("participant_list", {
    "participants": get_participant_list()
}, to=sid)
```

Modify `on_disconnect()`:
```python
# Decrement connection count
email = client_info.get("email")
current_count = participants.get(email, {}).get("connection_count", 1)
new_count = max(0, current_count - 1)

update_participant(email, {"connection_count": new_count})
```

**3. New WebSocket Events**

**`participant_list`** (server → client):
```json
{
  "participants": [
    {
      "email": "alice@example.com",
      "display_name": "Alice",
      "connection_count": 1,
      "status": "active"
    },
    {
      "email": "bob@example.com",
      "display_name": null,
      "connection_count": 0,
      "status": "offline"
    }
  ]
}
```

**`get_participant_list`** (client → server):
```json
{}  // Request full participant list
```

Response: `participant_list` event with full list

### Web Client Changes

**Location**: `src/roomz/server/pages/chat/chat.js`

**1. Add Participant Panel to Template**

```vue
<v-layout v-if="authenticated" style="height:100vh;">
  <v-app-bar ...>...</v-app-bar>

  <v-main>
    <v-container fluid style="height: 100%; display: flex; padding: 8px;">
      <!-- Messages Card (flex: 1) -->
      <v-card style="flex: 1; display: flex; flex-direction: column;">
        <v-card-text ref="messagesContainer">...</v-card-text>
      </v-card>

      <!-- Participants Panel (width: 250px, hide on mobile) -->
      <v-card
        v-if="showParticipants"
        style="width: 250px; margin-left: 8px;"
        class="d-none d-sm-flex"
      >
        <v-card-text>
          <div class="text-subtitle-2 mb-2">Participants</div>
          <div v-for="participant in sortedParticipants" :key="participant.email">
            <div class="d-flex align-center mb-2">
              <v-icon
                :color="participant.status === 'active' ? 'success' : 'grey'"
                size="small"
              >mdi-circle</v-icon>
              <span class="ml-2 text-body-2">
                {{ formatParticipantName(participant) }}
              </span>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </v-container>
  </v-main>

  <v-footer ...>...</v-footer>
</v-layout>
```

**2. Add Data Properties**

```javascript
data() {
  return {
    connected: false,
    messages: [],
    messageInput: '',
    sending: false,
    displayName: null,
    participants: []  // NEW
  };
}
```

**3. Add Computed Properties**

```javascript
computed: {
  showParticipants() {
    // Hide on very narrow screens (< 600px)
    return this.$vuetify.display.width >= 600;
  },
  sortedParticipants() {
    // Sort: active first, then offline, both alphabetically
    return [...this.participants].sort((a, b) => {
      // Active before offline
      if (a.status !== b.status) {
        return a.status === 'active' ? -1 : 1;
      }
      // Alphabetical by display name or email
      const nameA = a.display_name || a.email;
      const nameB = b.display_name || b.email;
      return nameA.localeCompare(nameB);
    });
  }
}
```

**4. Add Methods**

```javascript
methods: {
  formatParticipantName(participant) {
    if (participant.display_name) {
      return `${participant.display_name} (${participant.email})`;
    }
    return participant.email;
  },
  updateParticipantList(participants) {
    this.participants = participants;
  }
}
```

**5. Add Socket Event Listeners**

```javascript
mounted() {
  // ... existing listeners ...

  socket.on('participant_list', (data) => {
    this.updateParticipantList(data.participants);
  });
}

beforeUnmount() {
  // ... existing cleanup ...
  socket.off('participant_list');
}
```

**6. Request Participant List on Connect**

```javascript
socket.on('authenticated', (data) => {
  console.log("Authenticated as", data.user?.email);

  // Send display name if stored
  if (this.displayName) {
    this.setDisplayName(this.displayName);
  }

  // Request participant list
  socket.emit('get_participant_list');
});
```

### Python CLI Changes

**Location**: `src/roomz/cli/app_tui.py`

**1. Add Command Handler**

```python
async def handle_input(self, text: str) -> None:
    # ... existing commands ...

    if text == "/who":
        await self.show_participants()
        return

    # ... rest of command handling ...
```

**2. Add Participant List Method**

```python
async def show_participants(self) -> None:
    """Display the list of participants with status."""
    if not self.client.connected:
        self.add_error_message("Not connected. Use /login <email> then /token <token>")
        return

    # Request participant list from server
    result = await self.client.get_participant_list()

    if "error" in result:
        self.add_error_message(f"Failed to get participants: {result['error']}")
        return

    participants = result.get("participants", [])

    # Separate online and offline
    online = [p for p in participants if p.get("connection_count", 0) > 0]
    offline = [p for p in participants if p.get("connection_count", 0) == 0]

    # Format output
    output = [f"Participants ({len(online)} online, {len(offline)} offline):\n"]

    if online:
        output.append("\n[bold]Online:[/bold]")
        for p in sorted(online, key=lambda x: x.get("display_name") or x["email"]):
            name = self._format_participant_name(p)
            output.append(f"  ● {name}")

    if offline:
        output.append("\n[bold]Offline:[/bold]")
        for p in sorted(offline, key=lambda x: x.get("display_name") or x["email"]):
            name = self._format_participant_name(p)
            output.append(f"  ○ {name}")

    self.add_system_message("\n".join(output))

def _format_participant_name(self, participant: dict[str, Any]) -> str:
    """Format participant display name and email."""
    email = participant.get("email", "unknown")
    display_name = participant.get("display_name")
    if display_name and display_name.strip():
        return f"{display_name.strip()} ({email})"
    return email
```

**3. Add Client Library Support**

**Location**: `src/roomz/client/async_client.py`

```python
async def get_participant_list(self) -> dict[str, Any]:
    """
    Request the current participant list from the server.

    Returns:
        dict with 'participants' list or 'error'
    """
    if not self.connected:
        return {"error": "Not connected", "code": 400}

    return await self._emit_with_ack("get_participant_list", {})
```

**4. Register Event Handler**

```python
def _setup_client_handlers(self) -> None:
    # ... existing handlers ...
    self.client.on("participant_list", self._handle_participant_list)

async def _handle_participant_list(self, data: dict[str, Any]) -> None:
    """Handle participant list update from server."""
    # Store for later retrieval if needed
    self._participant_list = data.get("participants", [])
```

### Database Persistence (Future Phase)

**Note**: Not in MVP scope, but design for it.

**Schema** (MongoDB):
```javascript
{
  "email": "alice@example.com",
  "user_id": "user:alice@example.com",
  "display_name": "Alice",
  "first_seen": ISODate("2026-06-07T10:00:00Z"),
  "last_active": ISODate("2026-06-07T15:30:00Z"),
  "channels": ["user:alice@example.com"]  // For future multi-room support
}
```

**Migration Path**:
1. MVP: In-memory `participants` dict
2. Phase 2: Add MongoDB collection for participants
3. Hybrid: In-memory cache + async write-through to DB

## UI/UX Considerations

### Web Client

**Desktop (≥ 600px width)**:
- Participant panel on right side, fixed width 250px
- Always visible
- Scrollable if many participants
- Status indicators clearly visible (green/gray dots)

**Mobile (< 600px width)**:
- Participant panel hidden by default
- Icon button in app bar to show participant list
- Bottom sheet overlay when activated
- Tap outside to dismiss

**Accessibility**:
- Participant panel has `role="list"` and `aria-label="Participants"`
- Status indicators have `aria-label="online"` or `aria-label="offline"`
- Keyboard navigation: Tab to participant list, arrow keys to navigate

### Python CLI

**Command Output**:
- Clear separation between online and offline
- Visual indicators: ● for online, ○ for offline
- Alphabetical sorting within each group
- Count summary: "(3 online, 2 offline)"

**Integration**:
- `/who` command added to help text
- Works alongside existing commands
- No impact on message flow

## Protocol Changes

### New WebSocket Events

**Server → Client**:

1. **`participant_list`**
   - Triggered: On connect, and when participant list changes
   - Payload: `{"participants": [ParticipantInfo, ...]}`

2. **`participant_joined`**
   - Triggered: When a new participant joins for the first time
   - Payload: `{"participant": ParticipantInfo}`

3. **`participant_left`**
   - Triggered: When a participant's last connection closes
   - Payload: `{"participant": ParticipantInfo}`

**Client → Server**:

1. **`get_participant_list`**
   - Request: `{}`
   - Response: `participant_list` event

**Backward Compatibility**:
- Existing clients that don't handle `participant_list` will ignore it
- No breaking changes to existing events
- New events are additive only

### Message Format

**ParticipantInfo Object**:
```typescript
interface ParticipantInfo {
  email: string;              // Primary identifier
  user_id: string;            // Unique user ID
  display_name?: string;      // Optional display name
  first_seen: string;         // ISO 8601 timestamp
  last_active: string;        // ISO 8601 timestamp
  connection_count: number;   // Active connections (0 = offline)
  status: "active" | "offline";  // Computed from connection_count
}
```

## Acceptance Criteria

### AC1: Web Client Participant Display

**Given**: Multiple users are connected to the same room
**When**: User views the chat interface
**Then**:
- ✅ All participants are visible in right sidebar (desktop) or bottom sheet (mobile)
- ✅ Active participants show green dot indicator
- ✅ Offline participants show gray dot indicator
- ✅ Participants sorted: active first, then offline, alphabetically within groups
- ✅ Display name shown as "{name} ({email})", fallback to email if no name

### AC2: Real-time Participant Updates

**Given**: User is viewing the participant list
**When**: Another user joins or leaves
**Then**:
- ✅ Participant list updates immediately (no page refresh)
- ✅ Connection counts reflect current state
- ✅ Status indicators change (active ↔ offline) as appropriate

### AC3: Python CLI `/who` Command

**Given**: User is connected via CLI
**When**: User types `/who`
**Then**:
- ✅ List shows all participants separated into online/offline groups
- ✅ Online participants marked with ●
- ✅ Offline participants marked with ○
- ✅ Count summary displayed: "(X online, Y offline)"
- ✅ Display names formatted correctly

### AC4: New User Experience

**Given**: New user connects for first time
**When**: Connection established
**Then**:
- ✅ User appears in participant list immediately
- ✅ All existing participants see the new user
- ✅ User sees all existing participants
- ✅ Connection count = 1 for new user

### AC5: Multi-device User

**Given**: User connects from two devices (same email)
**When**: Viewing participant list
**Then**:
- ✅ User appears once in participant list
- ✅ Connection count = 2
- ✅ Status shows "active"
- ✅ When one device disconnects, count decreases to 1
- ✅ When both disconnect, status changes to "offline"

### AC6: Display Name Changes

**Given**: User has display name set
**When**: User changes display name
**Then**:
- ✅ Participant list updates immediately for all users
- ✅ New display name visible in participant list

### AC7: Server Restart Resilience

**Given**: Users are connected and visible in participant list
**When**: Server restarts
**Then**:
- ✅ Participant list is lost (in-memory storage)
- ✅ On reconnect, participants are re-added
- ✅ New participant list built from reconnected users

**Note**: Database persistence (Phase 2) will preserve participant list across restarts.

## Dependencies

### Task Dependencies

- **I11-001** (Participant Status with typing indicator): Builds on this task
  - I11-001 will add: typing indicators, custom status, idle detection
  - Design participant list to support future status types

- **No blocking dependencies**: This task can proceed independently

### Technical Dependencies

- Current architecture uses in-memory connection tracking
- No database required for MVP
- Web client: Vue 3 + Vuetify 4 already in use
- Python CLI: Textual framework already in use
- WebSocket: Socket.IO already integrated

## Risks and Mitigations

### Risk 1: Performance with Many Participants

**Risk**: Broadcasting full participant list on every join/leave could be expensive with 100+ users.

**Mitigation**:
- Send delta updates instead of full list (send only changed participant)
- Throttle updates (max 1 update per second)
- Scale test with simulated 100+ connections

**MVP Decision**: Accept performance risk for simplicity. Optimize in Phase 2.

### Risk 2: Memory Usage

**Risk**: Participant list grows unbounded over time (offline users accumulate).

**Mitigation**:
- Add TTL for offline participants (e.g., remove after 30 days offline)
- Configurable `PARTICIPANT_TTL_DAYS` environment variable
- Admin command to clean up stale participants

**MVP Decision**: No TTL in MVP. Accept memory growth. Add in Phase 2.

### Risk 3: Mobile Screen Space

**Risk**: Participant panel takes valuable screen space on mobile.

**Mitigation**:
- Hide panel by default on mobile (< 600px)
- Show via overlay/bottom sheet
- Icon button in app bar to toggle visibility
- Clear dismiss affordance (tap outside)

**MVP Decision**: Implement mobile-friendly overlay approach.

### Risk 4: Privacy Concerns

**Risk**: Users may not want to be visible to all participants.

**Mitigation**:
- Current design: Private channels already limit visibility to user's own channel
- Participant list breaks this privacy model
- Consider: Only show participants who have explicitly "joined" the room
- Future: Add "invisible" mode for privacy

**MVP Decision**: Document that joining makes user visible to all. Accept current privacy model.

## Implementation Plan

### Phase 1: Server-Side Infrastructure (2-3 hours)

1. Add `participants` dict to server
2. Create `update_participant()` function
3. Modify `on_connect()` to register participants
4. Modify `on_disconnect()` to update participant status
5. Add `participant_list` broadcast event
6. Add `get_participant_list` request handler

### Phase 2: Web Client UI (2-3 hours)

1. Add participant panel to Vue template
2. Add computed properties for sorted participants
3. Add socket event listener for `participant_list`
4. Request participant list on connect
5. Test on desktop and mobile viewports

### Phase 3: Python CLI Command (1-2 hours)

1. Add `/who` command to input handler
2. Add `get_participant_list()` method to AsyncClient
3. Format and display participant list
4. Test with multiple clients

### Phase 4: Testing & Polish (2-3 hours)

1. Test with multiple users joining/leaving
2. Test display name changes
3. Test multi-device same user
4. Test mobile responsive layout
5. Add help text for `/who` command
6. Update documentation

**Total Estimate**: 7-11 hours

## Testing Strategy

### Unit Tests

**Server**:
- `test_participant_registry`: Verify add/update/remove operations
- `test_connection_count`: Verify multi-device counting
- `test_participant_list_broadcast`: Verify broadcast on changes

**Client Library**:
- `test_get_participant_list`: Verify request/response

### Integration Tests

**Web Client**:
- Multiple browser tabs: Verify participant list consistency
- Join/leave: Verify real-time updates
- Display name change: Verify list updates

**Python CLI**:
- `/who` command: Verify output format
- Multi-client: Verify consistency across clients

### Manual Testing

1. **Desktop Browser**:
   - Open 3 browser tabs with different accounts
   - Verify all 3 users appear in participant list
   - Close one tab, verify status changes
   - Change display name, verify update

2. **Mobile Browser**:
   - Open on mobile device
   - Verify participant panel hidden
   - Tap icon to show participant list
   - Verify overlay appears

3. **Python CLI**:
   - Connect with `/login` and `/token`
   - Run `/who` command
   - Verify output format
   - Connect second client, verify count increase

## Documentation Updates

### README.md

Add to "How to Use" section:

```markdown
### Viewing Participants

**Web Client**: The participant list is always visible in the right sidebar (desktop) or accessible via the participants icon in the app bar (mobile).

**Python CLI**: Use the `/who` command to list all participants:

```
/who
Participants (3 online, 2 offline):

Online:
  ● Alice (alice@example.com)
  ● Charlie (charlie@example.com)
  ● Dave (dave@example.com)

Offline:
  ○ Bob (bob@example.com)
  ○ Eve (eve@example.com)
```
```

### CHANGELOG.md

Add entry:

```markdown
## [Unreleased]

### Added
- Participant list display showing all users in the room with online/offline status
- Web client: Right sidebar (desktop) or overlay (mobile) for participant visibility
- Python CLI: `/who` command to list participants with status indicators
- Real-time participant updates when users join/leave
```

## Open Questions

### Q1: Should offline participants be removed after a TTL?

**Options**:
- A. Never remove (accumulates forever)
- B. Remove after N days of inactivity (configurable TTL)
- C. Remove on server restart (memory only, no persistence)

**Recommendation**: Option B for Phase 2 (database persistence). Option C for MVP (in-memory only).

### Q2: Should participant list be scoped to channels or global?

**Current**: Private channels (`user:{email}`)

**Options**:
- A. Global participant list (all users who have ever connected)
- B. Per-channel participant list (requires room concept)

**Recommendation**: Option A for MVP. Aligns with current single-room architecture. Future multi-room support (Phase 2) will need Option B.

### Q3: How to handle "invisible" mode for privacy?

**Options**:
- A. Not supported (everyone is visible)
- B. User preference: "Show me in participant list" (default: yes)
- C. Admin-managed: Some users can be invisible

**Recommendation**: Defer to Phase 2. MVP does not support invisible mode.

## Conclusion

This feature provides essential visibility into who is present in a room, enabling better coordination for multi-agent scenarios. The implementation builds on existing presence infrastructure while adding persistent tracking and user-friendly display. The design accommodates future enhancements (typing indicators, custom status, database persistence) without creating technical debt.