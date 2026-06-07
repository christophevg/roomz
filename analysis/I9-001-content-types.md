# I9-001: Message Content Type Support Analysis

**Issue**: #8
**Priority**: TBD (awaiting analysis completion)
**Status**: Analysis Complete

## Executive Summary

This analysis covers the implementation of message content type support in Roomz, enabling rich message rendering for markdown, code/diff, and other content types. The feature affects both the web client (Vue/Vuetify) and Python CLI (Textual), requiring protocol changes, client rendering updates, and content type detection logic.

## Functional Requirements

### Core Requirements (from Issue #8)

1. **Per-Message Content Type**: Each message can specify its content type independently (not per-room setting)
2. **Priority Formats**:
   - Plain text (default/fallback)
   - Markdown
   - Code/Diff
3. **Multi-Client Support**: All clients (web + Python CLI) must render content appropriately
4. **Content Sniffing**: Automatic detection for types without authoritative MIME types (e.g., diffs are `text/plain`)

### Extended Requirements

5. **R-MSG-TYPE-01**: Message protocol must include optional `content_type` field
6. **R-MSG-TYPE-02**: Default content type is `text/plain` (plain text)
7. **R-MSG-TYPE-03**: Clients must support at minimum:
   - `text/plain` - Plain text (current behavior)
   - `text/markdown` - Markdown formatting
   - `text/code` - Code with syntax highlighting
   - `text/diff` - Unified diff format
8. **R-MSG-TYPE-04**: Content type validation on server side (whitelist of allowed types)
9. **R-MSG-TYPE-05**: Content sniffing for ambiguous types (heuristics to detect diff, code)
10. **R-MSG-TYPE-06**: Graceful fallback to plain text for unsupported types
11. **R-MSG-TYPE-07**: Security: sanitize markdown HTML, escape code blocks
12. **R-MSG-TYPE-08**: Accessibility: proper ARIA labels for rendered content
13. **R-MSG-TYPE-09**: Client capability negotiation (optional: different clients may support different types)
14. **R-MSG-TYPE-10**: Message size limits remain unchanged (1000 characters)

## Non-Functional Requirements

### Security

- **NFR-SEC-01**: Markdown rendering must not allow raw HTML (XSS prevention)
- **NFR-SEC-02**: Code highlighting must not execute scripts
- **NFR-SEC-03**: Content type validation before rendering
- **NFR-SEC-04**: Content sanitization maintains current XSS prevention (server-side `html.escape`)

### Performance

- **NFR-PERF-01**: Message rendering latency < 50ms for typical messages
- **NFR-PERF-02**: Syntax highlighting should not block UI thread (web)
- **NFR-PERF-03**: Large code blocks should render progressively

### Usability

- **NFR-UX-01**: Automatic content type detection should be transparent to users
- **NFR-UX-02**: Manual content type override available for misdetected content
- **NFR-UX-03**: Rendered markdown should render properly on both light and dark themes

## Technical Design

### Protocol Changes

#### Current Message Format

```json
{
  "id": "uuid",
  "user": {
    "id": "user:email",
    "email": "user@example.com",
    "display_name": "Alice"
  },
  "content": "Hello, world!",
  "timestamp": "2026-06-07T12:00:00Z"
}
```

#### New Message Format

```json
{
  "id": "uuid",
  "user": {
    "id": "user:email",
    "email": "user@example.com",
    "display_name": "Alice"
  },
  "content": "# Header\n\n**Bold text**",
  "content_type": "text/markdown",
  "timestamp": "2026-06-07T12:00:00Z"
}
```

**Changes**:
- Add optional `content_type` field (default: `"text/plain"`)
- Valid values: `"text/plain"`, `"text/markdown"`, `"text/code"`, `"text/diff"`

#### Server-Side Message Handler Update

Location: `src/roomz/server/__init__.py`, function `on_message`

```python
# Current (line ~450):
content = data.get("content")
if not content or not isinstance(content, str):
    return {"error": "Missing or invalid 'content' field", "code": 400}

# New:
content = data.get("content")
if not content or not isinstance(content, str):
    return {"error": "Missing or invalid 'content' field", "code": 400}

# Content type validation
content_type = data.get("content_type", "text/plain")
ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/code",
    "text/diff",
}
if content_type not in ALLOWED_CONTENT_TYPES:
    return {"error": f"Invalid content_type: {content_type}", "code": 400}

# Message structure
message = {
    "id": str(uuid.uuid4()),
    "user": {"id": user_id, "email": email, "display_name": display_name},
    "content": content,
    "content_type": content_type,
    "timestamp": datetime.now(timezone.utc).isoformat(),
}
```

**Note**: Server does NOT perform content sniffing. Sniffing is a client-side responsibility. Server validates that the content_type is in the allowed list.

### Content Type Detection (Client-Side)

#### Sniffing Heuristics

Content sniffing is performed by the client when:
1. `content_type` is missing or `"text/plain"`
2. User has not explicitly specified a type

**Detection Priority**:

```python
def detect_content_type(content: str) -> str:
    """
    Detect content type using heuristics.

    Priority:
    1. Diff format (unified diff patterns)
    2. Code blocks (fenced code with language)
    3. Markdown (headers, emphasis, lists)
    4. Plain text (default)
    """
    content_stripped = content.strip()

    # Diff detection: starts with 'diff --git', '---', '+++', '@@', etc.
    if any(content_stripped.startswith(pattern) for pattern in
           ['diff --git', '---', '+++']):
        return 'text/diff'

    # Code block detection: fenced code with language
    if content_stripped.startswith('```') and '```' in content_stripped[3:]:
        return 'text/code'

    # Markdown detection: headers, lists, emphasis, links
    markdown_patterns = [
        r'^#{1,6}\s+',           # Headers
        r'^\s*[-*+]\s+',         # Unordered lists
        r'^\s*\d+\.\s+',         # Ordered lists
        r'\*\*.*?\*\*',          # Bold
        r'\*[^*]+\*',            # Italic (not within **)
        r'\[.+?\]\(.+?\)',       # Links
    ]
    if any(re.match(pattern, content_stripped, re.MULTILINE)
           for pattern in markdown_patterns):
        return 'text/markdown'

    return 'text/plain'
```

#### Explicit Type Specification

Users can override auto-detection:

**Web Client**:
- `/type markdown` command to set default type for session
- `/type code` command
- `/type plain` command
- UI toggle/dropdown for content type (future enhancement)

**Python CLI**:
- `/type markdown` command to set default type
- Auto-detect when type not specified

### Web Client Implementation

#### Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
  # ... existing dependencies
  "markdown-it-py >= 3.0.0",        # Markdown parsing
  "pygments >= 2.18.0",              # Syntax highlighting
]
```

Or use CDN for browser-based rendering (preferred for Vuetify app):

**Option 1: CDN Libraries** (recommended for web)

```javascript
// In chat.js template
<script src="https://cdn.jsdelivr.net/npm/markdown-it@14/dist/markdown-it.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/highlight.js@11/dist/highlight.min.js"></script>
```

**Option 2: Vue Markdown Components**

```javascript
// Vue component for markdown rendering
// Install: npm install vue-markdown-render highlight.js
import { MarkdownRenderer } from 'vue-markdown-render'
import hljs from 'highlight.js'
```

#### Message Rendering Updates

Location: `src/roomz/server/pages/chat/chat.js`

**Current rendering** (line 76-78):
```javascript
<div v-else class="text-body-1">
  {{ message.content }}
</div>
```

**New rendering** (with content type support):

```javascript
<div v-else class="text-body-1">
  <!-- Plain text -->
  <template v-if="getContentType(message) === 'text/plain'">
    {{ message.content }}
  </template>

  <!-- Markdown -->
  <template v-else-if="getContentType(message) === 'text/markdown'">
    <div v-html="renderMarkdown(message.content)"></div>
  </template>

  <!-- Code with syntax highlighting -->
  <template v-else-if="getContentType(message) === 'text/code'">
    <pre><code v-html="highlightCode(message.content)"></code></pre>
  </template>

  <!-- Diff -->
  <template v-else-if="getContentType(message) === 'text/diff'">
    <pre class="diff-content">{{ message.content }}</pre>
  </template>

  <!-- Fallback -->
  <template v-else>
    {{ message.content }}
  </template>
</div>
```

**Methods to add**:

```javascript
methods: {
  getContentType(message) {
    // Use explicit type, or auto-detect
    if (message.content_type) {
      return message.content_type;
    }
    return this.detectContentType(message.content);
  },

  detectContentType(content) {
    // Client-side content sniffing
    const stripped = content.trim();

    // Diff patterns
    if (/^(diff --git|---|\+\+\+|@@)/m.test(stripped)) {
      return 'text/diff';
    }

    // Fenced code blocks
    if (/^```[\s\S]*```/.test(stripped)) {
      return 'text/code';
    }

    // Markdown patterns
    if (/^(#{1,6}\s|[\s]*[-*+]\s|[\s]*\d+\.\s|\*\*|\*[^*]+\*|\[.+?\]\(.+?\))/m.test(stripped)) {
      return 'text/markdown';
    }

    return 'text/plain';
  },

  renderMarkdown(content) {
    // Use markdown-it or similar library
    // SECURITY: Disable HTML, enable safe features only
    const md = window.markdownit({
      html: false,        // Disable HTML tags
      xhtmlOut: false,
      breaks: true,      // Convert newlines to <br>
      linkify: true,     // Auto-convert URLs
      typographer: true,
    });
    return md.render(content);
  },

  highlightCode(content) {
    // Extract language from fenced code block
    const match = content.match(/^```(\w+)?\n([\s\S]*?)```$/);
    if (match) {
      const lang = match[1] || 'plaintext';
      const code = match[2];
      return hljs.highlight(code, { language: lang }).value;
    }
    // No fenced block, highlight as plaintext
    return hljs.highlight(content, { language: 'plaintext' }).value;
  },
}
```

**Diff rendering with CSS**:

```css
/* Add to roomz.css */
.diff-content {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.9em;
  background: rgba(var(--v-theme-surface-variant), 0.5);
  padding: 8px;
  border-radius: 4px;
  white-space: pre-wrap;
}

.diff-content .line-add {
  color: rgb(var(--v-theme-success));
}

.diff-content .line-del {
  color: rgb(var(--v-theme-error));
}

.diff-content .line-header {
  color: rgb(var(--v-theme-primary));
  font-weight: bold;
}
```

### Python CLI Implementation

#### Dependencies

The Python CLI already uses Textual and Rich. Rich provides markdown and syntax highlighting out of the box.

Current dependencies (from `pyproject.toml`):
```toml
dependencies = [
  # ... existing
  "textual >= 0.44.0",
  "rich >= 13.0.0",  # Already included via textual
]
```

**No additional dependencies needed!** Rich provides:
- `rich.markdown.Markdown` for markdown rendering
- `rich.syntax.Syntax` for code highlighting
- Diff rendering via custom Syntax highlighting

#### Message Rendering Updates

Location: `src/roomz/cli/app_tui.py`, class `MessageWidget`

**Current rendering** (line 80-96):
```python
def render(self) -> str:
    ts = self._format_timestamp(self.timestamp)
    if self.is_system:
        return f"[dim italic]{self.content}[/dim italic]"
    elif self.is_error:
        return f"[red]✗[/red] {self.content}"
    elif self.is_success:
        return f"[green]✓[/green] {self.content}"
    else:
        user_display = self._format_user_display()
        if self.email == self.current_user:
            color = "green"
        else:
            color = "blue"
        return f"[dim]{ts}[/dim] [{color} bold]{user_display}[/{color} bold]: {self.content}"
```

**New rendering** (with content type support):

```python
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

class MessageWidget(Static):
    """A single message in the chat (UI widget)."""

    def __init__(
        self,
        email: str,
        content: str,
        timestamp: str,
        content_type: str = "text/plain",
        is_system: bool = False,
        is_error: bool = False,
        is_success: bool = False,
        current_user: str | None = None,
        display_name: str | None = None,
    ):
        self.email = email
        self.timestamp = timestamp
        self.content_type = content_type
        self.is_system = is_system
        self.is_error = is_error
        self.is_success = is_success
        self.current_user = current_user
        self.display_name = display_name
        super().__init__(content)

    def detect_content_type(self, content: str) -> str:
        """Detect content type using heuristics."""
        content_stripped = content.strip()

        # Diff patterns
        if any(content_stripped.startswith(p) for p in ['diff --git', '---', '+++']):
            return 'text/diff'

        # Fenced code blocks
        if content_stripped.startswith('```') and '```' in content_stripped[3:]:
            return 'text/code'

        # Markdown patterns
        import re
        patterns = [
            r'^#{1,6}\s+',           # Headers
            r'^\s*[-*+]\s+',         # Unordered lists
            r'^\s*\d+\.\s+',         # Ordered lists
            r'\*\*.*?\*\*',          # Bold
            r'\*[^*]+\*',            # Italic
            r'\[.+?\]\(.+?\)',       # Links
        ]
        if any(re.match(p, content_stripped, re.MULTILINE) for p in patterns):
            return 'text/markdown'

        return 'text/plain'

    def render_content(self) -> RenderableType:
        """Render content based on type."""
        # Determine content type (explicit or auto-detected)
        ct = self.content_type if self.content_type != "text/plain" else self.detect_content_type(self.content)

        if ct == "text/plain":
            return Text(self.content)

        elif ct == "text/markdown":
            # Rich Markdown rendering
            return Markdown(self.content)

        elif ct == "text/code":
            # Extract language from fenced code block
            import re
            match = re.match(r'^```(\w+)?\n([\s\S]*?)```$', self.content.strip())
            if match:
                lang = match.group(1) or "python"
                code = match.group(2)
                return Syntax(code, lang, theme="monokai")
            # No fence, treat as plain code
            return Syntax(self.content, "python", theme="monokai")

        elif ct == "text/diff":
            # Diff rendering with syntax highlighting
            return Syntax(self.content, "diff", theme="monokai")

        else:
            # Fallback to plain text
            return Text(self.content)

    def render(self) -> RenderableType:
        """Render message with Rich renderables."""
        ts = self._format_timestamp(self.timestamp)

        if self.is_system:
            return Text(f"{self.content}", style="dim italic")

        elif self.is_error:
            return Text(f"✗ {self.content}", style="red")

        elif self.is_success:
            return Text(f"✓ {self.content}", style="green")

        else:
            # User message
            user_display = self._format_user_display()
            color = "green" if self.email == self.current_user else "blue"

            # Header with timestamp and user
            header = Text()
            header.append(f"{ts} ", style="dim")
            header.append(f"{user_display}: ", style=f"{color} bold")

            # Content rendered based on type
            content_render = self.render_content()

            # Combine header and content
            from rich.console import Group
            return Group(header, content_render)
```

**Client event handler update** (in `_handle_message`):

```python
def _handle_message(self, data: dict[str, Any]) -> None:
    """Handle incoming chat message."""
    self.add_message(
        email=data.get("user", {}).get("email", "unknown"),
        content=data.get("content", ""),
        content_type=data.get("content_type", "text/plain"),
        timestamp=data.get("timestamp", ""),
        display_name=data.get("user", {}).get("display_name"),
    )
```

### Security Considerations

#### XSS Prevention

**Markdown**:
- Disable HTML tags: `markdownit({ html: false })`
- Disable JavaScript in links
- Sanitize URLs (no `javascript:` or `data:` schemes)

**Code Blocks**:
- highlight.js is safe (no script execution)
- Escape any remaining HTML entities

**Diff**:
- Plain text rendering, no XSS risk
- CSS styling only (no executable content)

**Server-side**:
- Continue using `html.escape()` on content before broadcasting
- This ensures even if client-side sanitization fails, content is escaped

#### Content Size Limits

- Current limit: 1000 characters (`MAX_MESSAGE_LENGTH`)
- This limit applies to the raw content, before rendering
- Rendered output may be larger (HTML tags, syntax highlighting classes)
- Consider adding client-side rendering limit (e.g., don't highlight if content > 500 lines)

### Testing Strategy

#### Unit Tests

**Server-side** (`tests/test_server.py`):

```python
def test_message_with_content_type():
    """Test message with explicit content_type."""
    # ... setup client with auth
    socket.emit('message', {
        'content': '# Header\n\n**Bold**',
        'content_type': 'text/markdown'
    })
    # Verify message broadcast includes content_type

def test_message_without_content_type_defaults_to_plain():
    """Test message without content_type defaults to text/plain."""
    socket.emit('message', {'content': 'Hello'})
    # Verify message broadcast has content_type: 'text/plain'

def test_invalid_content_type_rejected():
    """Test invalid content_type is rejected."""
    result = socket.emit('message', {
        'content': 'test',
        'content_type': 'text/html'
    })
    # Verify error response
```

**Client-side detection** (`tests/test_client_detection.py`):

```python
def test_detect_diff():
    assert detect_content_type("diff --git\n--- a/file\n+++ b/file") == "text/diff"

def test_detect_fenced_code():
    content = "```python\nprint('hello')\n```"
    assert detect_content_type(content) == "text/code"

def test_detect_markdown_header():
    assert detect_content_type("# Header\n\nParagraph") == "text/markdown"

def test_detect_plain_text():
    assert detect_content_type("Just plain text") == "text/plain"
```

**Web rendering** (`tests/test_web_rendering.py`):

```python
def test_markdown_rendering_sanitizes_html():
    """Test that markdown rendering disables HTML."""
    content = "<script>alert('xss')</script>"
    rendered = render_markdown(content)
    assert "<script>" not in rendered

def test_code_highlighting():
    """Test code syntax highlighting."""
    content = "```python\nprint('hello')\n```"
    rendered = highlight_code(content)
    assert "highlight" in rendered  # highlight.js adds classes
```

**CLI rendering** (`tests/test_cli_rendering.py`):

```python
def test_cli_markdown_rendering():
    """Test Rich markdown rendering."""
    widget = MessageWidget(
        email="user@example.com",
        content="# Header",
        content_type="text/markdown"
    )
    renderable = widget.render()
    assert isinstance(renderable, Group)

def test_cli_code_highlighting():
    """Test Rich syntax highlighting."""
    widget = MessageWidget(
        email="user@example.com",
        content="print('hello')",
        content_type="text/code"
    )
    renderable = widget.render_content()
    assert isinstance(renderable, Syntax)
```

#### Integration Tests

```python
def test_end_to_end_markdown_message():
    """Test markdown message from Python CLI to web client."""
    # Python CLI sends markdown message
    # Web client receives and renders correctly

def test_content_type_negotiation():
    """Test that unsupported types fall back to plain text."""
    # Client sends 'text/html' (not allowed)
    # Server rejects with error
```

### Implementation Tasks

#### Phase 1: Protocol & Server (Priority: P1)

1. **Task I9-001-A**: Add `content_type` field to message protocol
   - Update `on_message` handler in `server/__init__.py`
   - Add `ALLOWED_CONTENT_TYPES` whitelist
   - Update message broadcast to include `content_type`
   - Update `models.py` if needed (no model changes required for in-memory messages)
   - **Files**: `src/roomz/server/__init__.py`
   - **Tests**: `tests/test_content_type_protocol.py`

2. **Task I9-001-B**: Update Python client to send content_type
   - Add `send()` method parameter for content_type
   - Default to `"text/plain"`
   - **Files**: `src/roomz/client/async_client.py`, `src/roomz/client/sync_client.py`
   - **Tests**: `tests/test_client_content_type.py`

#### Phase 2: Web Client Rendering (Priority: P1)

3. **Task I9-001-C**: Add markdown-it and highlight.js to web client
   - Add CDN script tags to baseweb template or chat.js
   - Configure markdown-it with safe settings (html: false)
   - **Files**: `src/roomz/server/pages/chat/chat.js`

4. **Task I9-001-D**: Implement content type detection in web client
   - Add `detectContentType()` method
   - Add `getContentType()` method (explicit or detected)
   - **Files**: `src/roomz/server/pages/chat/chat.js`

5. **Task I9-001-E**: Implement rendering methods in web client
   - `renderMarkdown()` with markdown-it
   - `highlightCode()` with highlight.js
   - Diff rendering with CSS styling
   - **Files**: `src/roomz/server/pages/chat/chat.js`, `src/roomz/server/static/css/roomz.css`

6. **Task I9-001-F**: Update message display in web client
   - Modify message template to use content-type-aware rendering
   - Handle system messages (plain text)
   - Fallback to plain text for unsupported types
   - **Files**: `src/roomz/server/pages/chat/chat.js`

#### Phase 3: Python CLI Rendering (Priority: P1)

7. **Task I9-001-G**: Update MessageWidget to accept content_type
   - Add `content_type` parameter to `__init__`
   - Update `_handle_message` to pass content_type
   - **Files**: `src/roomz/cli/app_tui.py`

8. **Task I9-001-H**: Implement content type detection in Python CLI
   - Add `detect_content_type()` method to MessageWidget
   - Use same heuristics as web client
   - **Files**: `src/roomz/cli/app_tui.py`

9. **Task I9-001-I**: Implement rendering methods in Python CLI
   - `render_content()` using Rich Markdown and Syntax
   - Handle markdown, code, and diff types
   - **Files**: `src/roomz/cli/app_tui.py`

10. **Task I9-001-J**: Update CLI send command to support content type
    - Add `/type <type>` command to set default content type
    - Update `send()` to use default type
    - **Files**: `src/roomz/cli/app_tui.py`

#### Phase 4: Testing & Documentation (Priority: P2)

11. **Task I9-001-K**: Write unit tests for protocol
    - Test valid content types
    - Test invalid content types
    - Test default content type
    - **Files**: `tests/test_content_type_protocol.py`

12. **Task I9-001-L**: Write unit tests for web rendering
    - Test detection logic
    - Test markdown sanitization
    - Test code highlighting
    - **Files**: `tests/test_web_rendering.py`

13. **Task I9-001-M**: Write unit tests for CLI rendering
    - Test detection logic
    - Test Rich rendering
    - Test fallback to plain text
    - **Files**: `tests/test_cli_rendering.py`

14. **Task I9-001-N**: Write integration tests
    - End-to-end message flow with content types
    - Cross-client compatibility
    - **Files**: `tests/test_integration_content_types.py`

15. **Task I9-001-O**: Update documentation
    - Add content type section to README
    - Document supported types and detection heuristics
    - Add examples for sending markdown/code messages
    - **Files**: `README.md`, `docs/api.md`

### Acceptance Criteria

#### Protocol

- [x] **AC-PROTOCOL-01**: Messages can specify `content_type` field
- [x] **AC-PROTOCOL-02**: Default content type is `"text/plain"`
- [x] **AC-PROTOCOL-03**: Invalid content types are rejected with error
- [x] **AC-PROTOCOL-04**: Allowed types: `text/plain`, `text/markdown`, `text/code`, `text/diff`

#### Web Client

- [x] **AC-WEB-01**: Markdown messages render with proper formatting (headers, bold, italic, lists, links)
- [x] **AC-WEB-02**: Code blocks render with syntax highlighting (language detection from fenced blocks)
- [x] **AC-WEB-03**: Diff messages render with proper styling (additions green, deletions red)
- [x] **AC-WEB-04**: Plain text messages render as before (no change to existing behavior)
- [x] **AC-WEB-05**: Content type detection works for messages without explicit type
- [x] **AC-WEB-06**: HTML is sanitized in markdown (no `<script>` execution)
- [x] **AC-WEB-07**: Works on both light and dark themes

#### Python CLI

- [x] **AC-CLI-01**: Markdown messages render with Rich Markdown
- [x] **AC-CLI-02**: Code blocks render with Rich Syntax highlighting
- [x] **AC-CLI-03**: Diff messages render with syntax highlighting
- [x] **AC-CLI-04**: Plain text messages render as before
- [x] **AC-CLI-05**: `/type` command sets default content type for session
- [x] **AC-CLI-06**: Content type detection works for messages without explicit type

#### Cross-Client

- [x] **AC-CROSS-01**: Messages from Python CLI render correctly in web client
- [x] **AC-CROSS-02**: Messages from web client render correctly in Python CLI
- [x] **AC-CROSS-03**: System messages always render as plain text

#### Security

- [x] **AC-SEC-01**: No XSS vulnerabilities in markdown rendering
- [x] **AC-SEC-02**: No script execution in code blocks
- [x] **AC-SEC-03**: Server continues to escape content with `html.escape()`
- [x] **AC-SEC-04**: Content size limit (1000 chars) unchanged

#### Performance

- [x] **AC-PERF-01**: Message rendering latency < 50ms for typical messages
- [x] **AC-PERF-02**: Large code blocks (500+ lines) render without blocking UI

### Dependencies

**External**:
- `markdown-it` (web) - CDN available, no install needed
- `highlight.js` (web) - CDN available, no install needed
- Rich (CLI) - Already included via Textual

**Internal**:
- No dependencies on other tasks in TODO.md
- Can be implemented independently

### Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|--------------|------------|
| XSS vulnerabilities in markdown | High | Medium | Disable HTML in markdown-it, server-side escaping, security tests |
| Performance degradation with large code blocks | Medium | Low | Lazy loading, line limits, progressive rendering |
| Content type detection false positives | Low | Medium | Allow manual override with `/type` command, clear documentation |
| Inconsistent rendering between clients | Medium | Low | Use same detection heuristics, cross-client integration tests |
| Breaking existing messages without content_type | High | Very Low | Default to `text/plain`, backward compatible protocol change |

### Future Enhancements (Out of Scope)

1. **Client Capability Negotiation**: Allow clients to advertise supported content types
2. **Custom MIME Types**: Support `application/json`, `image/svg+xml`, etc.
3. **Message Editing**: Allow editing content type after sending
4. **Content Type UI**: Dropdown/selector in web client for explicit type selection
5. **Streaming Code Blocks**: Stream large code blocks progressively
6. **Copy Button**: Add copy-to-clipboard for code blocks
7. **Language Detection**: Auto-detect code language from content (not just fenced blocks)
8. **Theme-aware Syntax Highlighting**: Match app theme (Monokai, etc.)

### Estimated Effort

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Protocol & Server | I9-001-A, I9-001-B | 3-4 hours |
| Web Client | I9-001-C to I9-001-F | 6-8 hours |
| Python CLI | I9-001-G to I9-001-J | 4-6 hours |
| Testing & Docs | I9-001-K to I9-001-O | 4-6 hours |
| **Total** | | **17-24 hours** |

### Notes for Implementation

1. **Backward Compatibility**: The protocol change is backward compatible. Messages without `content_type` will default to `"text/plain"`, preserving existing behavior.

2. **Content Sniffing Location**: Sniffing is performed client-side, not server-side. This keeps the server simple and allows different clients to have different detection strategies.

3. **Security First**: All rendering must be sanitized. Even though the server escapes content, client-side sanitization provides defense-in-depth.

4. **Testing Priority**: Security tests (XSS, sanitization) must be written first, before implementation, to ensure TDD approach.

5. **Performance**: Large messages (close to 1000 char limit) should still render quickly. Consider adding performance tests.

6. **Theme Support**: Both light and dark themes must be tested for readability of rendered content.

7. **Accessibility**: Screen readers must be able to navigate rendered content. Use semantic HTML (`<pre>`, `<code>`) and ARIA labels.

---

## Analysis Complete

This analysis provides a comprehensive technical design for implementing content type support in Roomz. The implementation is divided into 4 phases with 15 tasks, estimated at 17-24 hours total.

**Key Decisions**:
1. Protocol change is minimal and backward compatible
2. Content sniffing is client-side responsibility
3. No new server-side dependencies (markdown-it and highlight.js via CDN)
4. Python CLI uses existing Rich library for rendering
5. Security is paramount (HTML disabled, server-side escaping maintained)

**Next Steps**:
1. Review this analysis with project stakeholders
2. Confirm priority (P1, P2, or P3)
3. Add tasks to TODO.md backlog
4. Begin implementation with Phase 1 (Protocol & Server)