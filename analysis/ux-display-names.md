# UX/UI Analysis: Per-Device Display Names (I7-001)

**Project**: Roomz - Real-time Chatroom Web Service
**Task**: I7-001 - Per-device display names
**Date**: 2026-05-18
**Analyst**: UI/UX Designer Agent

## Executive Summary

This document outlines the UX design for per-device display names in Roomz. Display names allow users to set custom names for each device/session, making it easier to identify which device sent a message when a user has multiple active sessions (e.g., "Laptop", "Phone", "Work Computer").

The design follows existing patterns from the codebase:
- Command-based input (consistent with Python CLI)
- Client-side state persistence (localStorage, similar to authentication session)
- Minimal UI footprint (no additional dialogs or settings screens)

## 1. User Flow Overview

### 1.1 Setting Display Name Flow

```
User types "/name My Laptop" in chat input
  -> Client detects slash command
    -> Extract display name "My Laptop"
    -> Validate name (max length, no newlines)
    -> Store in localStorage
    -> Send to server via 'set_display_name' event
    -> Server broadcasts updated presence to user's channel
    -> UI shows confirmation message
    -> Subsequent messages show "My Laptop (user@email.com)"
```

### 1.2 Changing Display Name Flow

```
User types "/name New Name" in chat input
  -> Client detects slash command
    -> Extract new display name
    -> Validate and update localStorage
    -> Send update to server
    -> Server broadcasts presence update
    -> UI shows confirmation message
    -> Messages now show new name
```

### 1.3 Clearing Display Name Flow

```
User types "/name" (empty) in chat input
  -> Client detects slash command with no argument
    -> Remove display name from localStorage
    -> Send clear event to server
    -> Server broadcasts presence update
    -> UI shows confirmation message
    -> Messages revert to showing just email
```

### 1.4 User Experience Goals

1. **Low Friction**: Single command, no dialogs, no separate settings page
2. **Immediate Feedback**: Confirmation message shows new display name
3. **Persistent**: Display name survives page reloads and browser restarts
4. **Per-Device**: Each browser/device can have its own display name
5. **Reversible**: Easy to change or remove display name

## 2. Command Design

### 2.1 Command Syntax

| Command | Action | Result |
|---------|--------|--------|
| `/name My Laptop` | Set display name | Shows "My Laptop (user@email.com)" on messages |
| `/name Work` | Set display name | Shows "Work (user@email.com)" on messages |
| `/name` | Clear display name | Shows just "user@email.com" on messages |

### 2.2 Command Validation

```javascript
// Client-side validation rules
const DISPLAY_NAME_MAX_LENGTH = 50;
const DISPLAY_NAME_MIN_LENGTH = 1;

function validateDisplayName(name) {
  if (!name) return { valid: true }; // Empty is allowed (clears name)

  if (name.length < DISPLAY_NAME_MIN_LENGTH) {
    return { valid: false, error: 'Display name must be at least 1 character' };
  }

  if (name.length > DISPLAY_NAME_MAX_LENGTH) {
    return { valid: false, error: 'Display name must be 50 characters or less' };
  }

  // Prevent newlines (security/usability)
  if (name.includes('\n') || name.includes('\r')) {
    return { valid: false, error: 'Display name cannot contain newlines' };
  }

  // Prevent command injection
  if (name.startsWith('/')) {
    return { valid: false, error: 'Display name cannot start with /' };
  }

  // Trim whitespace
  const trimmed = name.trim();
  if (trimmed.length === 0) {
    return { valid: true }; // Treat as clearing name
  }

  return { valid: true, name: trimmed };
}
```

### 2.3 Command Processing Flow

```javascript
// In chat.js - sendMessage method
sendMessage() {
  const input = this.messageInput.trim();
  if (!input) return;

  // Check for slash commands
  if (input.startsWith('/name ')) {
    const displayName = input.slice(6).trim();
    this.handleSetDisplayName(displayName);
    this.messageInput = '';
    return;
  }

  if (input === '/name') {
    this.handleClearDisplayName();
    this.messageInput = '';
    return;
  }

  // Regular message (existing logic)
  // ...
}

handleSetDisplayName(name) {
  const validation = validateDisplayName(name);
  if (!validation.valid) {
    this.addSystemMessage(validation.error);
    return;
  }

  const trimmedName = validation.name;
  if (trimmedName) {
    // Store in localStorage
    localStorage.setItem('roomz_display_name', trimmedName);

    // Update local state
    this.displayName = trimmedName;

    // Send to server
    socket.emit('set_display_name', { display_name: trimmedName });

    // Show confirmation
    this.addSystemMessage(`Display name set to: ${trimmedName}`);
  } else {
    // Empty string - clear name
    this.handleClearDisplayName();
  }
}

handleClearDisplayName() {
  // Remove from localStorage
  localStorage.removeItem('roomz_display_name');

  // Clear local state
  this.displayName = null;

  // Notify server
  socket.emit('set_display_name', { display_name: null });

  // Show confirmation
  this.addSystemMessage('Display name cleared. Messages will show your email only.');
}
```

## 3. Local Storage Schema

### 3.1 Storage Key

```javascript
// Key: 'roomz_display_name'
// Value: String (display name) or not set

// Get display name
const displayName = localStorage.getItem('roomz_display_name');

// Set display name
localStorage.setItem('roomz_display_name', 'My Laptop');

// Clear display name
localStorage.removeItem('roomz_display_name');
```

### 3.2 Integration with Existing Session

The display name is stored separately from the authentication session. This ensures:

1. **Independence**: Display name changes don't affect authentication
2. **Per-Device**: Each browser maintains its own display name
3. **Simplicity**: No complex session object updates

### 3.3 State Synchronization

```javascript
// On page load (mounted or created)
mounted() {
  // ... existing socket setup ...

  // Load display name from localStorage
  this.displayName = localStorage.getItem('roomz_display_name');

  // After authentication, send display name to server
  socket.on('authenticated', (data) => {
    // ... existing auth handling ...

    // Send display name if set
    if (this.displayName) {
      socket.emit('set_display_name', { display_name: this.displayName });
    }
  });
}
```

## 4. Message Display Format

### 4.1 Message Component Update

```javascript
// Updated message display in Chat component
<div class="text-caption text-medium-emphasis" style="margin-bottom: 4px;">
  <span v-if="!message.system">
    <strong>{{ formatUserDisplayName(message.user) }}</strong>
    <span style="margin-left: 8px; opacity: 0.7;">
      {{ formatTime(message.timestamp) }}
    </span>
  </span>
  <span v-else>
    {{ formatTime(message.timestamp) }}
  </span>
</div>

// New method
methods: {
  formatUserDisplayName(user) {
    if (!user) return 'Unknown';

    const email = user.email || 'Unknown';
    const displayName = user.display_name;

    if (displayName) {
      return `${displayName} (${email})`;
    }
    return email;
  }
}
```

### 4.2 Display Name Formatting

| Scenario | Display Format |
|----------|---------------|
| Display name set | `"My Laptop (user@email.com)"` |
| No display name | `"user@email.com"` |
| Unknown user | `"Unknown"` |

### 4.3 Visual Hierarchy

```html
<!-- Message header with display name -->
<div class="message-header">
  <strong class="display-name">My Laptop</strong>
  <span class="email-address">(user@email.com)</span>
  <span class="timestamp">12:34 PM</span>
</div>
```

```css
/* Styling for display name hierarchy */
.display-name {
  /* Primary - the name the user chose */
  font-weight: 600;
  color: var(--v-theme-on-surface);
}

.email-address {
  /* Secondary - email in parentheses */
  font-size: 0.85em;
  opacity: 0.7;
  margin-left: 4px;
}

.timestamp {
  /* Tertiary - time of message */
  opacity: 0.5;
  margin-left: 8px;
}
```

### 4.4 Message Structure (Server Broadcast)

```javascript
// Server broadcasts message with display name
{
  id: 'uuid',
  user: {
    id: 'user-id',
    email: 'user@email.com',
    display_name: 'My Laptop'  // NEW: optional display name
  },
  content: 'Hello!',
  timestamp: '2026-05-18T12:34:56.789Z'
}

// Server broadcasts presence event with display name
{
  user: {
    id: 'user-id',
    email: 'user@email.com',
    display_name: 'My Laptop'  // NEW: optional display name
  },
  timestamp: '2026-05-18T12:34:56.789Z',
  total_connections: 2
}
```

## 5. Presence Event Display

### 5.1 User Joined Message

```javascript
// Current format
socket.on('user_joined', (data) => {
  const email = data.user ? data.user.email : 'Unknown';
  this.addMessage({
    id: `system-${Date.now()}`,
    system: true,
    content: `${email} joined`,
    timestamp: data.timestamp
  });
});

// Updated format with display name
socket.on('user_joined', (data) => {
  const displayName = this.formatUserDisplayName(data.user);
  this.addMessage({
    id: `system-${Date.now()}`,
    system: true,
    content: `${displayName} joined`,
    timestamp: data.timestamp
  });
});
```

### 5.2 User Left Message

```javascript
// Updated format with display name
socket.on('user_left', (data) => {
  const displayName = this.formatUserDisplayName(data.user);
  this.addMessage({
    id: `system-${Date.now()}`,
    system: true,
    content: `${displayName} left`,
    timestamp: data.timestamp
  });
});
```

### 5.3 Multi-Device Awareness

When a user has multiple devices with different display names:

```javascript
// User joins from "Laptop" (already has "Phone" connected)
// Broadcast: "Laptop (user@email.com) joined"
// Existing devices see: "Laptop (user@email.com) joined"
// Other users see: "Laptop (user@email.com) joined"

// Presence list shows:
// - user@email.com (Laptop) - connected
// - user@email.com (Phone) - connected
```

## 6. Server-Side Integration

### 6.1 WebSocket Events (Coordinate with API Architect)

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `set_display_name` | Client -> Server | `{ display_name: string | null }` | Set or clear display name |
| `authenticated` | Server -> Client | `{ user: { id, email, display_name }, ... }` | Updated to include display_name |
| `message` | Server -> Client | `{ user: { id, email, display_name }, content, timestamp }` | Updated to include display_name |
| `user_joined` | Server -> Client | `{ user: { id, email, display_name }, timestamp, total_connections }` | Updated to include display_name |
| `user_left` | Server -> Client | `{ user: { id, email, display_name }, timestamp, remaining_connections }` | Updated to include display_name |

### 6.2 Server Behavior (Stateless)

```python
# Server-side pseudocode (coordinate with API Architect)
@server.socketio.on('set_display_name')
async def on_set_display_name(sid: str, data: dict) -> dict:
    """
    Handle display name update from client.

    Display names are NOT stored on the server. They are attached
    to each connection and broadcast with presence events.

    Args:
        sid: Socket session ID
        data: { display_name: string | null }

    Returns:
        { status: 'ok' } or { status: 'error', error: '...' }
    """
    client_info = connected_clients.get(sid)
    if not client_info:
        return { 'status': 'error', 'error': 'Not authenticated' }

    display_name = data.get('display_name')

    # Validate
    if display_name is not None:
        if len(display_name) > 50:
            return { 'status': 'error', 'error': 'Display name too long' }
        if '\n' in display_name or '\r' in display_name:
            return { 'status': 'error', 'error': 'Display name cannot contain newlines' }

    # Store on connection (in-memory only)
    client_info['display_name'] = display_name

    # Broadcast presence update to user's channel
    email = client_info['email']
    user_id = client_info['user_id']
    user_channel = USER_CHANNEL_FORMAT.format(email)

    await server.socketio.emit(
        'presence_update',
        {
            'user': {
                'id': user_id,
                'email': email,
                'display_name': display_name
            },
            'timestamp': datetime.now(timezone.utc).isoformat(),
        },
        room=user_channel
    )

    return { 'status': 'ok' }
```

### 6.3 Display Name Propagation

```python
# When broadcasting messages, include display_name
async def on_message(sid: str, data: dict) -> dict:
    client_info = connected_clients.get(sid)
    if not client_info:
        return { 'error': 'Not authenticated' }

    message = {
        'id': str(uuid.uuid4()),
        'user': {
            'id': client_info.get('user_id'),
            'email': client_info.get('email'),
            'display_name': client_info.get('display_name')  # NEW
        },
        'content': content,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    # Broadcast...
```

## 7. App Bar User Menu Update

### 7.1 Current User Display

The app bar currently shows just the email. Update to show display name when set:

```javascript
<!-- App Bar User Menu -->
<v-menu v-if="currentUser">
  <template v-slot:activator="{ props }">
    <v-btn v-bind="props" variant="text">
      <v-icon start>mdi-account</v-icon>
      {{ formatCurrentUserDisplay() }}
      <v-icon end>mdi-chevron-down</v-icon>
    </v-btn>
  </template>
  <v-list density="compact">
    <!-- Option to set/clear display name -->
    <v-list-item v-if="displayName" @click="showNameDialog = true">
      <v-list-item-title>
        <v-icon start>mdi-pencil</v-icon>
        Change Display Name
      </v-list-item-title>
    </v-list-item>
    <v-list-item v-else @click="showNameDialog = true">
      <v-list-item-title>
        <v-icon start>mdi-tag</v-icon>
        Set Display Name
      </v-list-item-title>
    </v-list-item>
    <v-divider></v-divider>
    <v-list-item @click="handleLogout">
      <v-list-item-title>
        <v-icon start>mdi-logout</v-icon>
        Sign Out
      </v-list-item-title>
    </v-list-item>
  </v-list>
</v-menu>
```

### 7.2 User Display Format Method

```javascript
computed: {
  currentUser() {
    return this.authenticated ? store.getters.session.user : null;
  },
  displayName() {
    return localStorage.getItem('roomz_display_name');
  }
},
methods: {
  formatCurrentUserDisplay() {
    const email = this.currentUser?.email || 'User';
    const displayName = this.displayName;

    // On mobile, show just the display name or truncated email
    if (this.isMobile) {
      return displayName || this.truncateEmail(email);
    }

    // On desktop, show full format
    if (displayName) {
      return displayName;
    }
    return email;
  },
  truncateEmail(email) {
    // For mobile: show first part of email
    if (email.includes('@')) {
      return email.split('@')[0];
    }
    return email.substring(0, 10);
  }
}
```

### 7.3 Mobile Considerations

For mobile devices with limited space in the app bar:

1. **Display Name Priority**: Show display name if set, otherwise truncated email
2. **Icon-Only Option**: Consider icon-only display on very narrow screens (320px)
3. **Responsive Breakpoint**: Switch to compact display at `xs` breakpoint (< 600px)

```javascript
computed: {
  isMobile() {
    return this.$vuetify.display.xs;
  }
}
```

## 8. Confirmation Messages

### 8.1 System Message Formatting

When a user sets or clears their display name, show a system message confirmation:

```javascript
// Setting display name
this.addMessage({
  id: `system-${Date.now()}`,
  system: true,
  content: `Display name set to: "${trimmedName}"`,
  timestamp: new Date().toISOString()
});

// Clearing display name
this.addMessage({
  id: `system-${Date.now()}`,
  system: true,
  content: 'Display name cleared. Messages will show your email only.',
  timestamp: new Date().toISOString()
});

// Error message
this.addMessage({
  id: `system-${Date.now()}`,
  system: true,
  content: `Error: ${error}`,
  timestamp: new Date().toISOString()
});
```

### 8.2 Visual Style for Confirmation Messages

System messages use distinct styling (already implemented):

```html
<div
  v-for="(message, index) in messages"
  :key="message.id || index"
  style="margin-bottom: 12px; padding: 8px; border-radius: 8px;"
  :style="{
    'background-color': message.system
      ? 'rgba(var(--v-theme-surface-variant))'
      : 'rgba(var(--v-theme-primary), 0.1)'
  }"
>
```

For display name confirmations, consider using a success color:

```javascript
// Optional: Add success styling for confirmation messages
{
  system: true,
  success: true,  // NEW flag
  content: 'Display name set to: "My Laptop"'
}

// In template
:style="{
  'background-color': message.success
    ? 'rgba(var(--v-theme-success), 0.1)'
    : message.system
      ? 'rgba(var(--v-theme-surface-variant))'
      : 'rgba(var(--v-theme-primary), 0.1)'
}"
```

## 9. Mobile Considerations

### 9.1 Input Field Design

The command input uses the existing message input field, which is already mobile-optimized:

- `density="comfortable"` for touch-friendly size
- `variant="outlined"` for clear input boundaries
- `clearable` for easy clearing
- `prepend-inner-icon="mdi-message-text"` for visual feedback

### 9.2 Command Help

Users may not know about the `/name` command. Consider adding help:

```javascript
// Add command help
// When user types "/", show available commands
handleInputChange() {
  if (this.messageInput === '/') {
    this.showCommandHelp = true;
  } else {
    this.showCommandHelp = false;
  }
}
```

```html
<!-- Command help overlay -->
<v-menu v-model="showCommandHelp" :close-on-content-click="false">
  <v-list density="compact">
    <v-list-item>
      <v-list-item-title><code>/name &lt;name&gt;</code> - Set display name</v-list-item-title>
    </v-list-item>
    <v-list-item>
      <v-list-item-title><code>/name</code> - Clear display name</v-list-item-title>
    </v-list-item>
  </v-list>
</v-menu>
```

### 9.3 Display Name Display on Mobile

On narrow screens (320px minimum), the display name format should adapt:

| Screen Width | Message Header Format |
|--------------|----------------------|
| >= 400px | `Display Name (email@example.com) 12:34 PM` |
| < 400px | `Display Name 12:34 PM` (email hidden) |
| < 400px, no name | `email@... 12:34 PM` (truncated) |

```javascript
formatUserDisplayName(user) {
  if (!user) return 'Unknown';

  const email = user.email || 'Unknown';
  const displayName = user.display_name;
  const isNarrow = this.$vuetify.display.width < 400;

  if (displayName) {
    if (isNarrow) {
      return displayName; // Just show name on narrow screens
    }
    return `${displayName} (${email})`;
  }

  if (isNarrow) {
    // Truncate email on narrow screens
    return email.length > 15 ? email.substring(0, 15) + '...' : email;
  }
  return email;
}
```

### 9.4 Touch Targets

- Command input: Already uses `density="comfortable"` (44px+ touch target)
- User menu: Vuetify `v-btn` defaults to adequate touch target
- System messages: No interactive elements

## 10. Accessibility

### 10.1 ARIA Labels

```html
<!-- Message input with command support -->
<v-text-field
  v-model="messageInput"
  placeholder="Type a message or /name YourName to set display name..."
  prepend-inner-icon="mdi-message-text"
  append-inner-icon="mdi-send"
  aria-label="Message input. Type /name followed by your name to set a display name."
  role="textbox"
  clearable
/>
```

### 10.2 Screen Reader Announcements

```javascript
// Announce display name changes
handleSetDisplayName(name) {
  // ... validation and storage ...

  this.announceToScreenReader(`Display name set to ${name}`);
  this.addSystemMessage(`Display name set to: ${name}`);
}

handleClearDisplayName() {
  // ... clear storage ...

  this.announceToScreenReader('Display name cleared');
  this.addSystemMessage('Display name cleared. Messages will show your email only.');
}
```

### 10.3 Keyboard Navigation

- `/name` command works with keyboard-only input
- Tab to message input, type command, press Enter
- No additional focus management needed

### 10.4 Color Contrast

Display name hierarchy uses text opacity rather than color changes:
- Display name: `font-weight: 600` (darker)
- Email: `opacity: 0.7` (slightly lighter)
- Timestamp: `opacity: 0.5` (lighter still)

This maintains contrast ratios while creating visual hierarchy.

## 11. Error Handling

### 11.1 Client-Side Validation Errors

| Error | User Message |
|-------|--------------|
| Name too long | "Display name must be 50 characters or less" |
| Name contains newlines | "Display name cannot contain newlines" |
| Name starts with `/` | "Display name cannot start with /" |
| Name too short (after trim) | Treated as clearing name |

### 11.2 Server-Side Errors

| Error Code | User Message |
|------------|--------------|
| `not_authenticated` | "You must be logged in to set a display name" |
| `name_too_long` | "Display name must be 50 characters or less" |
| `invalid_characters` | "Display name contains invalid characters" |

### 11.3 Network Errors

```javascript
// Handle network failures gracefully
socket.emit('set_display_name', { display_name: name }, (response) => {
  if (!response) {
    // Timeout or disconnection
    this.addSystemMessage('Connection lost. Display name saved locally but not synced.');
    return;
  }

  if (response.status === 'error') {
    this.addSystemMessage(`Error: ${response.error}`);
    return;
  }

  // Success - confirmation already shown
});
```

## 12. Testing Checklist

### 12.1 Functional Testing

- [ ] `/name My Laptop` sets display name
- [ ] `/name` clears display name
- [ ] Display name persists after page reload
- [ ] Display name shows in messages from this device
- [ ] Display name shows in messages from other devices (same user)
- [ ] Display name shows in user joined/left messages
- [ ] Display name shows in app bar (desktop)
- [ ] Display name truncated on mobile
- [ ] Validation: name too long shows error
- [ ] Validation: newlines show error
- [ ] Validation: empty command clears name
- [ ] Multiple devices can have different names
- [ ] Clearing name reverts to email-only display
- [ ] localStorage correctly stores/retrieves name

### 12.2 Accessibility Testing

- [ ] Screen reader announces display name changes
- [ ] ARIA labels present on message input
- [ ] Keyboard-only navigation works
- [ ] Color contrast meets WCAG 2.1 AA

### 12.3 Mobile Testing

- [ ] Works at 320px width
- [ ] Display name format adapts on narrow screens
- [ ] Command input accessible
- [ ] App bar shows appropriate content

### 12.4 Integration Testing

- [ ] Display name synced to server on connect
- [ ] Presence events include display name
- [ ] Messages include display name
- [ ] Reconnection preserves display name
- [ ] Logout does not clear display name (stays in localStorage)

## 13. Dependencies

### 13.1 Frontend Components (Existing)

| Component | Usage |
|-----------|-------|
| `v-text-field` | Message input (command parsing) |
| `v-menu` | User dropdown menu |
| `v-list` | Menu items |
| `v-icon` | Icons |

### 13.2 Server Requirements (Coordinate with API Architect)

| Requirement | Notes |
|-------------|-------|
| `set_display_name` event handler | Accepts display name, stores on connection |
| Update `authenticated` event | Include display_name in user object |
| Update `message` event | Include display_name in user object |
| Update `user_joined` event | Include display_name in user object |
| Update `user_left` event | Include display_name in user object |
| `presence_update` event (new) | Broadcast when display name changes |

## 14. Acceptance Criteria Mapping

| Requirement | Implementation |
|-------------|----------------|
| `/name <name>` command to set display name at any time | Command parsing in `sendMessage()` method |
| Web client stores in localStorage | `localStorage.setItem('roomz_display_name', name)` |
| Display name persists across page reloads | Load from localStorage on mount |
| Messages show `{display name} ({email})` format when set | `formatUserDisplayName()` method |
| Multiple devices for same user can have different names | Per-connection storage on server, localStorage on client |
| Unsetting name reverts to email-only display | Clear localStorage, send null to server |

## 15. Next Steps for Engineering

1. **Update `chat.js`**:
   - Add `displayName` to component data (loaded from localStorage)
   - Implement command parsing in `sendMessage()`
   - Add `formatUserDisplayName()` method
   - Add `handleSetDisplayName()` and `handleClearDisplayName()` methods
   - Update message rendering to use display name format
   - Send display name on `authenticated` event

2. **Server-side updates (coordinate with API Architect)**:
   - Add `set_display_name` event handler
   - Store display_name on connected_clients entry
   - Include display_name in all user object broadcasts

3. **Update app bar**:
   - Show display name in user menu
   - Add menu item to set/change display name (optional - command is primary method)

4. **Testing**:
   - Unit tests for command parsing
   - Integration tests for display name propagation
   - E2E tests for multi-device scenarios

---

**Document Version**: 1.0
**Last Updated**: 2026-05-18
**Related Documents**:
- `analysis/ux-chat-ui.md` - Chat interface design
- `analysis/ux-auth-I2-001.md` - Authentication dialog design
- `TODO.md` - Task I7-001 definition