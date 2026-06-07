# I9-004: Collapsible Messages with Subject

**Issue**: #11
**Status**: Ready for Analysis
**Priority**: TBD
**Related**: I9-001 (Message content types)

## Executive Summary

Add support for collapsible messages with optional subject and body structure. This enables sending large messages with short summaries, improving readability in chat interfaces. Messages can be collapsed/expanded by users, with intelligent default behaviors for new vs. historical messages.

## Problem Statement

Currently, all messages in Roomz are displayed in full, which creates usability issues when:
- Agents send long structured responses (code, analysis, documentation)
- Users need to quickly scan message history for relevant information
- Message bodies contain detailed content while only the summary matters for context

Collapsible messages solve this by allowing a subject line (summary) with an optional body (details), similar to email subject/body or Slack collapsible posts.

## Requirements

### From Issue Comments

**Subject Field**
- Subject is **optional**
- When missing: message displays as non-collapsible (current behavior)
- When present: message becomes collapsible

**Collapse State Defaults**
- **Global default**: Collapsed
- **User preference**: Override global default (e.g., always expanded)
- **Message preference**: Message can request to be open by default
- **Precedence**: User preference > Message preference > Global default
- **Historical messages**: Always collapsed (no localStorage tracking per message)

**Content Types**
- Collapse settings can be per content type (extension from I9-001)
- Catch-all default for content types without specific settings

**Scope**
- Collapsing only applies to messages **with subject**
- Simple messages (no subject) remain non-collapsible

**Subject Formatting**
- Support colors (text coloring)
- Support special characters
- Support icons/emoji

### Acceptance Criteria

#### Protocol Changes

1. **Message schema extension**
   - `subject`: optional string field
   - `collapsed`: optional boolean field (sender's preference for initial state)
   - Backward compatible: existing messages without subject work as before

2. **Validation**
   - Subject max length: configurable (recommend 200 characters)
   - Subject sanitization: HTML escape, strip newlines
   - Body remains optional (subject-only messages allowed)

#### Server Implementation

3. **Message handling**
   - Accept `subject` and `collapsed` fields in message payload
   - Sanitize subject (HTML escape, length limit)
   - Include fields in broadcast message
   - No server-side storage of collapsed state (stateless)

#### Web Client Implementation

4. **Rendering**
   - Collapsed view: shows subject with expand button
   - Expanded view: shows subject + body with collapse button
   - Non-collapsible messages (no subject): display as current

5. **Collapse state management**
   - Default: Global collapsed state (true by default)
   - User preference: localStorage setting for default collapsed state
   - Message preference: Honor `collapsed: false` from sender
   - Historical messages: Always collapsed
   - No per-message state persistence

6. **Subject formatting**
   - Support markdown-like formatting for colors (e.g., `**bold**`, `*italic*`)
   - Support emoji and special characters
   - XSS prevention: sanitize subject

7. **UI/UX**
   - Smooth collapse/expand animation (CSS transition)
   - Clear visual distinction between collapsed/expanded states
   - Keyboard accessible: Enter/Space to toggle
   - Screen reader support: aria-expanded attribute

#### Python Client Implementation

8. **CLI rendering**
   - Collapsed: Display subject with [+] indicator
   - Expanded: Display subject with [-] indicator + body
   - Toggle command: `/expand <message-id>` and `/collapse <message-id>`

9. **Session state**
   - Track collapsed/expanded state in memory during session
   - No persistence (reset on restart)
   - Historical messages: Always collapsed by default

#### Content Type Integration (Future)

10. **I9-001 dependency**
    - Collapse settings per content type (markdown, code, diff, etc.)
    - Content type can specify default collapsed state
    - User preference overrides content type default

## Technical Design

### 1. Protocol Changes

#### Message Payload (Client → Server)

```json
{
  "content": "Full message body...",
  "subject": "Short summary",          // Optional
  "collapsed": true                    // Optional, sender's preference
}
```

#### Broadcast Message (Server → Clients)

```json
{
  "id": "uuid",
  "user": {"id": "...", "email": "...", "display_name": "..."},
  "content": "Full message body...",
  "subject": "Short summary",          // Optional
  "collapsed": true,                    // Sender's preference
  "timestamp": "2026-06-07T12:00:00Z",
  "is_historical": false                // Server adds this field
}
```

**New fields:**
- `subject`: string | null (optional, max 200 chars)
- `collapsed`: boolean (optional, default true)
- `is_historical`: boolean (added by server for historical messages)

### 2. Server Implementation

#### Message Validation

```python
MAX_SUBJECT_LENGTH = 200

@server.socketio.on("message")
async def on_message(sid: str, data: dict[str, Any]) -> dict[str, Any]:
    # ... existing validation ...

    # Extract optional fields
    subject = data.get("subject")
    collapsed_preference = data.get("collapsed", True)

    # Validate subject
    if subject:
        if not isinstance(subject, str):
            return {"error": "Invalid 'subject' field", "code": 400}
        subject = html.escape(subject.strip())[:MAX_SUBJECT_LENGTH]
        # Strip newlines from subject
        subject = subject.replace("\n", " ").replace("\r", "")

    # Include in broadcast
    message = {
        "id": str(uuid.uuid4()),
        "user": {...},
        "content": content,
        "subject": subject,
        "collapsed": collapsed_preference if subject else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

**No storage**: Server doesn't track collapsed state per user or per message. All state is client-side.

### 3. Web Client Implementation

#### Component Structure

```vue
<div v-for="message in messages" :key="message.id">
  <!-- Non-collapsible (no subject) -->
  <div v-if="!message.subject" class="message-simple">
    <div class="message-header">
      <strong>{{ formatUserDisplayName(message.user) }}</strong>
      <span>{{ formatTime(message.timestamp) }}</span>
    </div>
    <div class="message-body">{{ message.content }}</div>
  </div>

  <!-- Collapsible (has subject) -->
  <div v-else class="message-collapsible">
    <div class="message-header">
      <strong>{{ formatUserDisplayName(message.user) }}</strong>
      <span>{{ formatTime(message.timestamp) }}</span>
    </div>
    <div class="message-subject" @click="toggleMessage(message)">
      <v-icon>{{ messageExpanded(message) ? 'mdi-chevron-down' : 'mdi-chevron-right' }}</v-icon>
      <span v-html="formatSubject(message.subject)"></span>
    </div>
    <div v-if="messageExpanded(message)" class="message-body">
      {{ message.content }}
    </div>
  </div>
</div>
```

#### State Management

```javascript
data() {
  return {
    // ... existing ...
    userCollapsePreference: null,  // null = no preference, true = collapse all, false = expand all
    expandedMessages: new Set(),   // Track which messages are expanded in this session
  };
},
computed: {
  defaultCollapsed() {
    // User preference > Global default
    return this.userCollapsePreference ?? true;
  }
},
methods: {
  messageExpanded(message) {
    // Historical messages always collapsed
    if (message.is_historical) return false;

    // User explicitly toggled this message
    if (this.expandedMessages.has(message.id)) return true;
    if (this.collapsedMessages.has(message.id)) return false;

    // User preference > Message preference > Global default
    if (this.userCollapsePreference !== null) {
      return !this.userCollapsePreference;
    }

    // Message preference
    if (message.subject && message.collapsed === false) {
      return true;  // Message requested to be open
    }

    // Global default: collapsed
    return false;
  },
  toggleMessage(message) {
    if (this.messageExpanded(message)) {
      this.expandedMessages.delete(message.id);
      this.collapsedMessages.add(message.id);
    } else {
      this.collapsedMessages.delete(message.id);
      this.expandedMessages.add(message.id);
    }
  },
  formatSubject(subject) {
    // Sanitize and format subject
    // Support: **bold**, *italic*, `code`, emoji
    let formatted = escapeHtml(subject);
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');
    formatted = formatted.replace(/`(.+?)`/g, '<code>$1</code>');
    return formatted;
  }
}
```

#### localStorage Settings

```javascript
// Load user preference on mount
mounted() {
  const saved = localStorage.getItem('collapsePreference');
  this.userCollapsePreference = saved === 'true' ? true : saved === 'false' ? false : null;
},

// Save user preference when changed
setCollapsePreference(collapsed) {
  this.userCollapsePreference = collapsed;
  if (collapsed === null) {
    localStorage.removeItem('collapsePreference');
  } else {
    localStorage.setItem('collapsePreference', collapsed);
  }
}
```

### 4. Python Client Implementation

#### CLI Rendering

```python
# In app_tui.py

def render_message(message: dict) -> str:
    """Render message for CLI display."""
    user = format_user_display_name(message['user'])
    timestamp = format_time(message['timestamp'])

    if not message.get('subject'):
        # Simple message
        return f"{user} [{timestamp}]: {message['content']}\n"

    # Collapsible message
    subject = message['subject']
    body = message['content']

    # Determine expanded state
    is_historical = message.get('is_historical', False)
    msg_id = message['id']

    # Historical always collapsed
    if is_historical:
        return f"{user} [{timestamp}]: [+] {subject}\n"

    # Check session state
    if msg_id in self.expanded_messages:
        indicator = "[-]"
        content = f"{subject}\n    {body}"
    else:
        indicator = "[+]"
        content = subject

    return f"{user} [{timestamp}]: {indicator} {content}\n"
```

#### Toggle Commands

```python
# Add to CLI command handler
async def handle_command(self, command: str):
    parts = command.split(maxsplit=1)
    cmd = parts[0]

    if cmd == '/expand':
        msg_id = parts[1] if len(parts) > 1 else None
        if msg_id:
            self.expanded_messages.add(msg_id)
        else:
            # Expand all collapsible messages
            for msg in self.messages:
                if msg.get('subject'):
                    self.expanded_messages.add(msg['id'])

    elif cmd == '/collapse':
        msg_id = parts[1] if len(parts) > 1 else None
        if msg_id:
            self.expanded_messages.discard(msg_id)
        else:
            # Collapse all
            self.expanded_messages.clear()

    # ... existing commands ...
```

### 5. Historical Messages

#### Server Detection

When persistence (I10-001) is implemented, the server will mark historical messages:

```python
# Future implementation (I10-001)
def get_historical_messages(user_email: str, last_message_id: str | None):
    messages = db.query("SELECT * FROM messages WHERE ...")
    for msg in messages:
        msg['is_historical'] = True
    return messages
```

#### Client Behavior

Historical messages are **always collapsed** regardless of user preferences:

```javascript
messageExpanded(message) {
  // Historical messages always collapsed
  if (message.is_historical) return false;
  // ... rest of logic
}
```

**Rationale**: Avoids storing per-message collapsed state for potentially thousands of historical messages. Users can expand historical messages manually, but they don't remember the state across sessions.

### 6. Content Type Integration (Future)

When I9-001 (Message content types) is implemented:

```javascript
// Per content type defaults
const CONTENT_TYPE_COLLAPSE_DEFAULTS = {
  'markdown': false,     // Markdown default expanded
  'code': true,          // Code default collapsed
  'diff': true,          // Diff default collapsed
  'plain': false,        // Plain text default expanded
};

messageExpanded(message) {
  // Historical always collapsed
  if (message.is_historical) return false;

  // User toggled state
  if (this.expandedMessages.has(message.id)) return true;
  if (this.collapsedMessages.has(message.id)) return false;

  // User preference (applies to all)
  if (this.userCollapsePreference !== null) {
    return !this.userCollapsePreference;
  }

  // Content type default
  const contentType = message.content_type || 'plain';
  const typeDefault = CONTENT_TYPE_COLLAPSE_DEFAULTS[contentType];

  // Message preference
  if (message.collapsed !== undefined) {
    return !message.collapsed;
  }

  // Content type default
  return !typeDefault;
}
```

## Implementation Tasks

### Phase 1: Protocol & Server

1. **Update message schema**
   - Add `subject` field (optional string, max 200 chars)
   - Add `collapsed` field (optional boolean, default true)
   - Add `is_historical` field (server-side only)

2. **Server validation**
   - Validate subject length and sanitize
   - Strip newlines from subject
   - Include fields in broadcast

3. **Backward compatibility**
   - Existing clients without subject support continue working
   - Messages without subject display as non-collapsible

### Phase 2: Web Client

4. **UI components**
   - Add collapsible message component
   - Add collapse/expand icons
   - Add toggle animation (CSS transition)

5. **State management**
   - Track expanded messages in session
   - Load user preference from localStorage
   - Respect message preference and historical flag

6. **Subject formatting**
   - Sanitize subject HTML
   - Support basic markdown (bold, italic, code)
   - Support emoji rendering

7. **Accessibility**
   - Keyboard navigation (Enter/Space to toggle)
   - Screen reader support (aria-expanded)
   - Focus management

### Phase 3: Python Client

8. **CLI rendering**
   - Display collapsed messages with [+] indicator
   - Display expanded messages with [-] indicator
   - Format subject with colors if possible

9. **Commands**
   - `/expand <msg-id>` or `/expand` (all)
   - `/collapse <msg-id>` or `/collapse` (all)
   - Track expanded state in session

### Phase 4: Documentation & Testing

10. **Documentation**
    - Update README with collapsible message usage
    - Document protocol changes
    - Document client library changes

11. **Testing**
    - Unit tests for server validation
    - Integration tests for collapse state
    - E2E tests for web client UI
    - CLI tests for expand/collapse commands

## Dependencies

### Required Dependencies

- None (backward compatible with existing clients)

### Future Dependencies

- **I9-001**: Message content types (for per-content-type collapse defaults)
- **I10-001**: Message history persistence (for historical message detection)

## Risks & Mitigations

### Risk 1: Performance with Many Collapsible Messages

**Impact**: Large numbers of collapsible messages could slow rendering

**Mitigation**:
- Use virtual scrolling (only render visible messages)
- Limit number of messages loaded initially
- Defer expensive formatting until expansion

### Risk 2: Subject Formatting Security

**Impact**: XSS vulnerabilities in subject line

**Mitigation**:
- HTML escape all subject content server-side
- Only allow safe markdown formatting
- No raw HTML in subject

### Risk 3: Historical Message State Explosion

**Impact**: Storing expanded/collapsed state for thousands of historical messages

**Mitigation**:
- Historical messages always collapsed (no state tracking)
- Only track state for current session messages
- Clear state on session disconnect

### Risk 4: Backward Compatibility

**Impact**: Older clients may not understand new fields

**Mitigation**:
- Fields are optional, defaults provided
- Clients ignore unknown fields gracefully
- Non-collapsible messages work as before

## Questions for Clarification

1. **Subject length limit**: Is 200 characters appropriate, or should it be configurable?
2. **Content type integration**: Should we wait for I9-001, or implement basic collapsible messages first?
3. **Message body**: Can a message have a subject but no body? (Currently: yes, allowed)
4. **Edit/Delete**: If message editing is added later, should subject be editable?
5. **Search**: Should search include subject, body, or both?

## Acceptance Criteria (Refined)

### Server

- [ ] Accept `subject` field in message payload (optional, max 200 chars)
- [ ] Accept `collapsed` field (optional, boolean)
- [ ] Sanitize subject (HTML escape, strip newlines)
- [ ] Broadcast message includes `subject` and `collapsed` fields
- [ ] Backward compatible with clients not supporting subjects
- [ ] No server-side storage of collapse state

### Web Client

- [ ] Display non-collapsible messages as before (no changes)
- [ ] Display collapsible messages with subject and expand/collapse toggle
- [ ] Collapsed: show subject with expand icon
- [ ] Expanded: show subject + body with collapse icon
- [ ] Smooth CSS transition animation
- [ ] User preference in localStorage (collapse all/expand all/no preference)
- [ ] Respect message `collapsed` preference
- [ ] Historical messages always collapsed
- [ ] Subject formatting: bold, italic, code, emoji
- [ ] Keyboard accessible (Enter/Space to toggle)
- [ ] Screen reader support (aria-expanded)

### Python Client

- [ ] Display collapsed: `[+] subject`
- [ ] Display expanded: `[-] subject` + indented body
- [ ] Commands: `/expand <id>`, `/collapse <id>`, `/expand`, `/collapse`
- [ ] Track expanded state in session memory
- [ ] Historical messages always collapsed

### Testing

- [ ] Server validation tests
- [ ] Web client rendering tests
- [ ] Python client rendering tests
- [ ] Backward compatibility tests
- [ ] Accessibility tests (keyboard, screen reader)

## Timeline Estimate

- **Phase 1** (Protocol & Server): 2-3 hours
- **Phase 2** (Web Client): 4-6 hours
- **Phase 3** (Python Client): 2-3 hours
- **Phase 4** (Testing & Docs): 2-3 hours

**Total**: 10-15 hours

## Priority Recommendation

**P2 (High)** - This feature significantly improves usability for large/structured messages, especially for agent-generated content. It's a prerequisite for content type integration (I9-001) and supports the agent coordination use case.

Should be implemented before or alongside I9-001 (Message content types).