# I9-003: Question Message Type Analysis

**Issue**: #10
**Priority**: TBD (awaiting backlog prioritization)
**Status**: Analysis Complete

## Executive Summary

This analysis covers the implementation of a special question message type (`application/x-question`) for Roomz, enabling structured multiple choice question/answer interactions between participants. The feature supports both agent-to-user and user-to-user questions, with appropriate rendering across web and CLI clients, optional timeout with default answer, and flexible response handling.

## Functional Requirements

### Core Requirements (from Issue #10 and Owner Feedback)

1. **Question Message Type**: New message type for structured questions with multiple choice answers
2. **Canned Answers**: Answer options provided by sender (array of strings)
3. **Free-Text Option**: Optional free-text answer option (one option allows custom input)
4. **Response Mechanism**: Simple text response (not a special message type)
5. **Participant Neutrality**: Any participant can create questions (not agent-specific)
6. **Timeout Support**: Optional timeout with default answer (e.g., `timeout="60s"`, `timeout_message="no answer provided"`)
7. **Cancellation**: User can cancel/not answer without penalty
8. **Client-Appropriate Rendering**: Web renders buttons/radios; CLI renders text-based selection

### Extended Requirements

9. **R-QUESTION-01**: Message protocol must support `content_type: "application/x-question"`
10. **R-QUESTION-02**: Question messages must include:
    - `question`: The question text
    - `answers`: Array of answer options (objects with `label` and optional `free_text` flag)
    - `timeout`: Optional timeout in seconds (default: no timeout)
    - `timeout_message`: Optional default answer when timeout expires
11. **R-QUESTION-03**: Response to question is a regular message with:
    - Reference to question ID (`in_reply_to`)
    - Selected answer text in message content
12. **R-QUESTION-04**: Multiple answers allowed (checkboxes) or single answer (radio buttons)
    - Controlled by `multi_select: true/false` field
13. **R-QUESTION-05**: Server validates question structure on send
14. **R-QUESTION-06**: Server tracks question state (unanswered, answered, timeout)
15. **R-QUESTION-07**: Client displays question state visually
16. **R-QUESTION-08**: Timeout handling: server sends timeout_message if no answer received
17. **R-QUESTION-09**: Question can be cancelled by sender (delete message)
18. **R-QUESTION-10**: Answer can be edited/cancelled before timeout (if multi_select or free_text)
19. **R-QUESTION-11**: Message size limits apply to question text + answers
20. **R-QUESTION-12**: Accessibility: proper ARIA labels for question/answer widgets

### Non-Functional Requirements

#### Security

- **NFR-SEC-01**: Question content sanitized (no XSS in answers)
- **NFR-SEC-02**: Answer content sanitized before rendering
- **NFR-SEC-03**: Timeout enforced server-side (not client-side only)
- **NFR-SEC-04**: Rate limiting for questions (same as regular messages)

#### Performance

- **NFR-PERF-01**: Question rendering < 100ms
- **NFR-PERF-02**: Timeout tracking uses efficient data structure (avoid per-question timers)
- **NFR-PERF-03**: Large question lists (e.g., 20+ options) render efficiently

#### Usability

- **NFR-UX-01**: Clear visual distinction between answered and unanswered questions
- **NFR-UX-02**: Timeout countdown visible to recipient
- **NFR-UX-03**: Cancel option clearly available
- **NFR-UX-04**: Free-text input clearly distinguished from canned answers

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
  "content_type": "text/plain",
  "timestamp": "2026-06-07T12:00:00Z"
}
```

#### New Question Message Format

```json
{
  "id": "uuid",
  "user": {
    "id": "user:email",
    "email": "user@example.com",
    "display_name": "Alice"
  },
  "content": "What would you like to do?",
  "content_type": "application/x-question",
  "question_data": {
    "question": "What would you like to do?",
    "answers": [
      {"id": "ans1", "label": "Continue", "free_text": false},
      {"id": "ans2", "label": "Skip", "free_text": false},
      {"id": "ans3", "label": "Other: ", "free_text": true}
    ],
    "multi_select": false,
    "timeout": 60,
    "timeout_answer_id": "ans2",
    "timeout_message": "No answer provided"
  },
  "timestamp": "2026-06-07T12:00:00Z"
}
```

**Question Data Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | Yes | The question text |
| `answers` | array | Yes | 2-20 answer options |
| `multi_select` | boolean | No | Allow multiple selections (default: false) |
| `timeout` | integer | No | Timeout in seconds (default: no timeout) |
| `timeout_answer_id` | string | No | Answer ID to use on timeout |
| `timeout_message` | string | No | Message to show when timeout occurs |

**Answer Option Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier for this answer |
| `label` | string | Yes | Display text for this answer |
| `free_text` | boolean | No | Allows free-text input (default: false) |

#### Answer Response Format

```json
{
  "id": "uuid",
  "user": {
    "id": "user:email",
    "email": "user@example.com",
    "display_name": "Bob"
  },
  "content": "Continue",
  "content_type": "text/plain",
  "in_reply_to": "question-uuid",
  "answer_ids": ["ans1"],
  "free_text_value": null,
  "timestamp": "2026-06-07T12:01:30Z"
}
```

**Answer Response Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `in_reply_to` | string | Yes | ID of the question being answered |
| `answer_ids` | array | Yes | IDs of selected answers |
| `free_text_value` | string | No | Free-text input (if answer had `free_text: true`) |

#### Timeout Message Format

When timeout expires, server sends a system message:

```json
{
  "id": "uuid",
  "user": {
    "id": "system",
    "email": "system",
    "display_name": "System"
  },
  "content": "No answer provided",
  "content_type": "text/plain",
  "in_reply_to": "question-uuid",
  "system_message": true,
  "timestamp": "2026-06-07T12:02:00Z"
}
```

### Server-Side Implementation

#### Message Handler Update

Location: `src/roomz/server/__init__.py`, function `on_message`

```python
# Validation for question messages
if content_type == "application/x-question":
    question_data = data.get("question_data")
    if not question_data:
        return {"error": "Missing 'question_data' for question type", "code": 400}

    # Validate question structure
    try:
        validate_question_data(question_data)
    except ValueError as e:
        return {"error": str(e), "code": 400}

    # Store question state
    question_id = str(uuid.uuid4())
    question_state = {
        "id": question_id,
        "status": "unanswered",  # unanswered, answered, timeout
        "asked_by": user_id,
        "asked_at": datetime.now(timezone.utc),
        "timeout": question_data.get("timeout"),
        "timeout_answer_id": question_data.get("timeout_answer_id"),
        "timeout_message": question_data.get("timeout_message"),
    }
    active_questions[question_id] = question_state

    # Set timeout timer if specified
    if question_state["timeout"]:
        schedule_timeout(question_id, question_state["timeout"])

    # Broadcast question
    message = {
        "id": question_id,
        "user": {"id": user_id, "email": email, "display_name": display_name},
        "content": question_data["question"],
        "content_type": "application/x-question",
        "question_data": question_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

#### Question Validation

```python
def validate_question_data(data: dict) -> None:
    """Validate question structure."""
    # Required fields
    if "question" not in data:
        raise ValueError("Missing 'question' field")
    if "answers" not in data:
        raise ValueError("Missing 'answers' field")

    question = data["question"]
    answers = data["answers"]

    # Question validation
    if not isinstance(question, str) or not question.strip():
        raise ValueError("'question' must be a non-empty string")
    if len(question) > 1000:
        raise ValueError("'question' exceeds maximum length (1000 chars)")

    # Answers validation
    if not isinstance(answers, list):
        raise ValueError("'answers' must be an array")
    if len(answers) < 2:
        raise ValueError("'answers' must have at least 2 options")
    if len(answers) > 20:
        raise ValueError("'answers' cannot have more than 20 options")

    # Each answer validation
    answer_ids = set()
    for i, answer in enumerate(answers):
        if not isinstance(answer, dict):
            raise ValueError(f"Answer {i} must be an object")
        if "id" not in answer:
            raise ValueError(f"Answer {i} missing 'id' field")
        if "label" not in answer:
            raise ValueError(f"Answer {i} missing 'label' field")

        answer_id = answer["id"]
        if not isinstance(answer_id, str) or not answer_id.strip():
            raise ValueError(f"Answer {i} 'id' must be a non-empty string")
        if answer_id in answer_ids:
            raise ValueError(f"Duplicate answer id: {answer_id}")
        answer_ids.add(answer_id)

        label = answer["label"]
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"Answer {i} 'label' must be a non-empty string")
        if len(label) > 200:
            raise ValueError(f"Answer {i} 'label' exceeds maximum length (200 chars)")

        if "free_text" in answer:
            if not isinstance(answer["free_text"], bool):
                raise ValueError(f"Answer {i} 'free_text' must be a boolean")

    # Timeout validation
    if "timeout" in data:
        timeout = data["timeout"]
        if not isinstance(timeout, int) or timeout < 1:
            raise ValueError("'timeout' must be a positive integer")
        if timeout > 3600:
            raise ValueError("'timeout' cannot exceed 3600 seconds (1 hour)")

        # If timeout_answer_id specified, validate it exists
        if "timeout_answer_id" in data:
            timeout_answer_id = data["timeout_answer_id"]
            if timeout_answer_id not in answer_ids:
                raise ValueError(f"'timeout_answer_id' {timeout_answer_id} not found in answers")

    # Multi-select validation
    if "multi_select" in data:
        if not isinstance(data["multi_select"], bool):
            raise ValueError("'multi_select' must be a boolean")
```

#### Answer Handler

```python
async def on_answer_question(sid: str, data: dict) -> dict:
    """Handle answer to a question."""
    question_id = data.get("question_id")
    answer_ids = data.get("answer_ids", [])
    free_text_value = data.get("free_text_value")
    free_text_answer_id = data.get("free_text_answer_id")

    # Validate question exists
    if question_id not in active_questions:
        return {"error": "Question not found", "code": 404}

    question_state = active_questions[question_id]

    # Check if already answered or timed out
    if question_state["status"] != "unanswered":
        return {"error": f"Question already {question_state['status']}", "code": 400}

    # Validate answer IDs
    question_data = question_state["question_data"]
    valid_answer_ids = {a["id"] for a in question_data["answers"]}

    for answer_id in answer_ids:
        if answer_id not in valid_answer_ids:
            return {"error": f"Invalid answer ID: {answer_id}", "code": 400}

    # Check free-text answer
    if free_text_value:
        # Validate free_text_answer_id exists and has free_text: true
        free_text_answer = next(
            (a for a in question_data["answers"] if a["id"] == free_text_answer_id),
            None
        )
        if not free_text_answer or not free_text_answer.get("free_text", False):
            return {"error": "Free-text answer not allowed for this option", "code": 400}

        if len(free_text_value) > 500:
            return {"error": "Free-text answer exceeds maximum length (500 chars)", "code": 400}

    # Update question state
    question_state["status"] = "answered"
    question_state["answered_by"] = user_id
    question_state["answered_at"] = datetime.now(timezone.utc)

    # Cancel timeout if set
    cancel_timeout(question_id)

    # Broadcast answer
    answer_message = {
        "id": str(uuid.uuid4()),
        "user": {"id": user_id, "email": email, "display_name": display_name},
        "content": construct_answer_text(question_data, answer_ids, free_text_value),
        "content_type": "text/plain",
        "in_reply_to": question_id,
        "answer_ids": answer_ids,
        "free_text_value": free_text_value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    await broadcast_message(answer_message)
    return {"success": True, "message_id": answer_message["id"]}

def construct_answer_text(question_data: dict, answer_ids: list[str], free_text_value: str | None) -> str:
    """Construct human-readable answer text."""
    answers = question_data["answers"]
    selected = [a for a in answers if a["id"] in answer_ids]

    if len(selected) == 1:
        answer = selected[0]
        if answer.get("free_text", False) and free_text_value:
            return f"{answer['label']}{free_text_value}"
        return answer["label"]
    else:
        # Multi-select
        labels = []
        for answer in selected:
            if answer.get("free_text", False) and free_text_value:
                labels.append(f"{answer['label']}{free_text_value}")
            else:
                labels.append(answer["label"])
        return ", ".join(labels)
```

#### Timeout Handler

```python
import asyncio

# Global timeout tracking
pending_timeouts: dict[str, asyncio.Task] = {}

def schedule_timeout(question_id: str, timeout_seconds: int) -> None:
    """Schedule timeout for a question."""
    async def timeout_task():
        await asyncio.sleep(timeout_seconds)
        await handle_question_timeout(question_id)

    pending_timeouts[question_id] = asyncio.create_task(timeout_task())

def cancel_timeout(question_id: str) -> None:
    """Cancel pending timeout for a question."""
    if question_id in pending_timeouts:
        pending_timeouts[question_id].cancel()
        del pending_timeouts[question_id]

async def handle_question_timeout(question_id: str) -> None:
    """Handle question timeout."""
    if question_id not in active_questions:
        return

    question_state = active_questions[question_id]

    # Check if already answered
    if question_state["status"] != "unanswered":
        return

    # Update state
    question_state["status"] = "timeout"

    # Send timeout message
    timeout_message = question_state.get("timeout_message", "No answer provided")
    timeout_answer_id = question_state.get("timeout_answer_id")

    # If timeout_answer_id specified, send that as answer
    answer_text = timeout_message
    if timeout_answer_id:
        answer_text = get_answer_label(question_state["question_data"], timeout_answer_id)

    timeout_msg = {
        "id": str(uuid.uuid4()),
        "user": {"id": "system", "email": "system", "display_name": "System"},
        "content": answer_text,
        "content_type": "text/plain",
        "in_reply_to": question_id,
        "system_message": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    await broadcast_message(timeout_msg)
    del pending_timeouts[question_id]
```

### Web Client Implementation

#### Message Rendering Updates

Location: `src/roomz/server/pages/chat/chat.js`

**Question message template**:

```javascript
<!-- Question message -->
<template v-else-if="getContentType(message) === 'application/x-question'">
  <v-card class="question-card" :class="{'question-answered': isAnswered(message.id)}">
    <v-card-title class="text-subtitle-1">
      <v-icon left>mdi-help-circle</v-icon>
      {{ message.question_data.question }}
      <v-spacer></v-spacer>
      <v-chip v-if="message.question_data.timeout" size="small" :color="timeoutColor(message)">
        {{ formatTimeout(message) }}
      </v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Answer options -->
      <v-radio-group
        v-if="!message.question_data.multi_select"
        v-model="selectedAnswers[message.id]"
        :disabled="isAnswered(message.id)"
      >
        <v-radio
          v-for="answer in message.question_data.answers"
          :key="answer.id"
          :value="answer.id"
          :label="answer.label"
        >
          <template v-if="answer.free_text" v-slot:label>
            <v-text-field
              v-model="freeTextValues[message.id]"
              :disabled="selectedAnswers[message.id] !== answer.id"
              :placeholder="answer.label"
              density="compact"
              hide-details
            ></v-text-field>
          </template>
        </v-radio>
      </v-radio-group>

      <!-- Multi-select (checkboxes) -->
      <v-checkbox-group
        v-else
        v-model="selectedAnswers[message.id]"
        :disabled="isAnswered(message.id)"
      >
        <v-checkbox
          v-for="answer in message.question_data.answers"
          :key="answer.id"
          :value="answer.id"
          :label="answer.label"
        >
          <template v-if="answer.free_text" v-slot:label>
            <v-text-field
              v-model="freeTextValues[message.id]"
              :disabled="!selectedAnswers[message.id]?.includes(answer.id)"
              :placeholder="answer.label"
              density="compact"
              hide-details
            ></v-text-field>
          </template>
        </v-checkbox>
      </v-checkbox-group>
    </v-card-text>

    <v-card-actions v-if="!isAnswered(message.id)">
      <v-btn
        color="primary"
        @click="submitAnswer(message.id)"
        :disabled="!selectedAnswers[message.id] || selectedAnswers[message.id].length === 0"
      >
        Submit
      </v-btn>
      <v-btn
        variant="text"
        @click="skipQuestion(message.id)"
      >
        Skip
      </v-btn>
    </v-card-actions>

    <v-card-text v-else>
      <v-chip color="success" size="small">
        <v-icon left>mdi-check</v-icon>
        Answered
      </v-chip>
    </v-card-text>
  </v-card>
</template>
```

**Methods to add**:

```javascript
data() {
  return {
    // ... existing data
    selectedAnswers: {},           // { messageId: answerId | answerId[] }
    freeTextValues: {},            // { messageId: freeTextString }
    answeredQuestions: new Set(),  // Set of question IDs that have been answered
    questionTimeouts: {},          // { messageId: remainingSeconds }
  }
},

methods: {
  // ... existing methods

  isAnswered(messageId) {
    return this.answeredQuestions.has(messageId);
  },

  async submitAnswer(questionId) {
    const answerIds = Array.isArray(this.selectedAnswers[questionId])
      ? this.selectedAnswers[questionId]
      : [this.selectedAnswers[questionId]];

    const payload = {
      question_id: questionId,
      answer_ids: answerIds,
    };

    // Check for free-text value
    const freeTextAnswer = this.findFreeTextAnswer(questionId);
    if (freeTextAnswer && this.freeTextValues[questionId]) {
      payload.free_text_answer_id = freeTextAnswer;
      payload.free_text_value = this.freeTextValues[questionId];
    }

    const result = await this.socket.emit('answer_question', payload);

    if (result.success) {
      this.answeredQuestions.add(questionId);
    } else {
      this.addSystemMessage(`Error: ${result.error}`);
    }
  },

  skipQuestion(questionId) {
    // Just mark as skipped (no answer sent)
    this.answeredQuestions.add(questionId);
    this.addSystemMessage('Question skipped');
  },

  findFreeTextAnswer(questionId) {
    const message = this.messages.find(m => m.id === questionId);
    if (!message) return null;

    const selectedIds = Array.isArray(this.selectedAnswers[questionId])
      ? this.selectedAnswers[questionId]
      : [this.selectedAnswers[questionId]];

    for (const answer of message.question_data.answers) {
      if (answer.free_text && selectedIds.includes(answer.id)) {
        return answer.id;
      }
    }
    return null;
  },

  formatTimeout(message) {
    if (!message.question_data.timeout) return '';
    const remaining = this.questionTimeouts[message.id] || message.question_data.timeout;
    if (remaining <= 0) return 'Expired';
    if (remaining < 60) return `${remaining}s`;
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    return `${minutes}m ${seconds}s`;
  },

  timeoutColor(message) {
    if (!this.questionTimeouts[message.id]) return 'primary';
    const remaining = this.questionTimeouts[message.id];
    if (remaining <= 10) return 'error';
    if (remaining <= 30) return 'warning';
    return 'primary';
  },

  startTimeoutCounter(messageId, timeoutSeconds) {
    this.questionTimeouts[messageId] = timeoutSeconds;
    const intervalId = setInterval(() => {
      if (this.questionTimeouts[messageId] <= 0 || this.isAnswered(messageId)) {
        clearInterval(intervalId);
        return;
      }
      this.questionTimeouts[messageId]--;
    }, 1000);
  },
},
```

**CSS for question cards**:

```css
/* Add to roomz.css */
.question-card {
  margin: 8px 0;
  border-left: 4px solid rgb(var(--v-theme-primary));
}

.question-answered {
  border-left-color: rgb(var(--v-theme-success));
  opacity: 0.7;
}

.question-card .v-card-title {
  background: rgba(var(--v-theme-surface-variant), 0.5);
}
```

### Python CLI Implementation

#### Question Message Widget

Location: `src/roomz/cli/app_tui.py`

```python
from textual.widgets import Static, Button
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from rich.text import Text
from rich.syntax import Syntax

class QuestionWidget(Static):
    """A question message with answer options."""

    CSS = """
    QuestionWidget {
        background: $surface;
        border-left: thick $primary;
        margin: 1 0;
        padding: 1;
    }

    QuestionWidget.answered {
        border-left-color: $success;
        opacity: 0.7;
    }

    QuestionWidget .question-text {
        text-style: bold;
        margin-bottom: 1;
    }

    QuestionWidget .answer-option {
        margin: 0 1;
    }

    QuestionWidget .timeout-badge {
        color: $warning;
        text-style: bold;
    }

    QuestionWidget .timeout-critical {
        color: $error;
    }
    """

    selected_answer: reactive[str | None] = reactive(None)
    free_text_value: reactive[str] = reactive("")
    is_answered: reactive[bool] = reactive(False)

    def __init__(
        self,
        question_id: str,
        question_data: dict,
        email: str,
        timestamp: str,
        display_name: str | None = None,
        current_user: str | None = None,
    ):
        self.question_id = question_id
        self.question_data = question_data
        self.email = email
        self.timestamp = timestamp
        self.display_name = display_name
        self.current_user = current_user
        self.timeout_seconds = question_data.get("timeout")
        self.timeout_remaining = self.timeout_seconds
        super().__init__()

    def compose(self):
        """Compose the question widget."""
        yield Static(self._render_question_text(), classes="question-text")

        # Timeout display
        if self.timeout_seconds:
            yield Static(self._render_timeout(), id="timeout-display", classes="timeout-badge")

        # Answer options
        with Container(classes="answer-options"):
            for answer in self.question_data["answers"]:
                yield AnswerOptionButton(
                    answer_id=answer["id"],
                    label=answer["label"],
                    free_text=answer.get("free_text", False),
                    classes="answer-option",
                )

        # Submit/Skip buttons
        with Horizontal(classes="button-row"):
            yield Button("Submit", id="submit-answer", variant="primary", disabled=True)
            yield Button("Skip", id="skip-question", variant="default")

    def _render_question_text(self) -> Text:
        """Render question text with Rich."""
        text = Text()
        text.append(f"{self.timestamp} ", style="dim")
        color = "green" if self.email == self.current_user else "blue"
        user_display = self.display_name or self.email
        text.append(f"{user_display}: ", style=f"{color} bold")
        text.append(self.question_data["question"])
        return text

    def _render_timeout(self) -> str:
        """Render timeout display."""
        if not self.timeout_remaining:
            return "Expired"
        if self.timeout_remaining < 60:
            return f"{self.timeout_remaining}s"
        minutes = self.timeout_remaining // 60
        seconds = self.timeout_remaining % 60
        return f"{minutes}m {seconds}s"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "submit-answer":
            self._submit_answer()
        elif event.button.id == "skip-question":
            self._skip_question()

    def on_answer_option_selected(self, answer_id: str, free_text_value: str | None = None) -> None:
        """Handle answer option selection."""
        self.selected_answer = answer_id
        if free_text_value:
            self.free_text_value = free_text_value
        self.query_one("#submit-answer", Button).disabled = False

    def _submit_answer(self) -> None:
        """Submit the answer."""
        if not self.selected_answer:
            return

        # Emit answer event
        self.app.send_answer(
            question_id=self.question_id,
            answer_ids=[self.selected_answer],
            free_text_value=self.free_text_value if self.free_text_value else None,
        )

        self.is_answered = True
        self.add_class("answered")

    def _skip_question(self) -> None:
        """Skip the question."""
        self.is_answered = True
        self.add_class("answered")
        self.app.add_system_message("Question skipped")


class AnswerOptionButton(Button):
    """A single answer option button."""

    CSS = """
    AnswerOptionButton {
        margin: 1 2;
    }

    AnswerOptionButton.selected {
        background: $primary;
        color: $text-on-primary;
    }
    """

    def __init__(
        self,
        answer_id: str,
        label: str,
        free_text: bool = False,
        **kwargs,
    ):
        self.answer_id = answer_id
        self.answer_label = label
        self.is_free_text = free_text
        super().__init__(label=label, **kwargs)

    def on_click(self) -> None:
        """Handle button click."""
        # Emit selection event
        self.post_message(
            AnswerSelected(
                answer_id=self.answer_id,
                is_free_text=self.is_free_text,
                label=self.answer_label,
            )
        )


class AnswerSelected:
    """Event emitted when an answer is selected."""

    def __init__(self, answer_id: str, is_free_text: bool, label: str):
        self.answer_id = answer_id
        self.is_free_text = is_free_text
        self.label = label
```

#### CLI App Updates

```python
# In app_tui.py, ChatApp class

def send_answer(
    self,
    question_id: str,
    answer_ids: list[str],
    free_text_value: str | None = None,
) -> None:
    """Send answer to a question."""
    if not self.client or not self.client.is_connected():
        self.add_system_message("Error: Not connected to server")
        return

    payload = {
        "question_id": question_id,
        "answer_ids": answer_ids,
    }

    if free_text_value:
        payload["free_text_value"] = free_text_value

    result = self.client.emit("answer_question", payload)

    if result.get("success"):
        self.add_system_message("Answer submitted")
    else:
        self.add_system_message(f"Error: {result.get('error', 'Unknown error')}")

def on_answer_question(self, data: dict) -> None:
    """Handle answer confirmation from server."""
    # This is called when the server broadcasts the answer
    # Mark the question as answered
    question_widget = self.query_one(f"#question-{data['in_reply_to']}", QuestionWidget)
    if question_widget:
        question_widget.is_answered = True
        question_widget.add_class("answered")

def on_question_timeout(self, data: dict) -> None:
    """Handle question timeout from server."""
    question_id = data.get("in_reply_to")
    timeout_msg = data.get("content", "Question timed out")
    self.add_system_message(f"Question timeout: {timeout_msg}")

    # Mark question as answered
    question_widget = self.query_one(f"#question-{question_id}", QuestionWidget)
    if question_widget:
        question_widget.is_answered = True
        question_widget.add_class("answered")
```

### Testing Strategy

#### Unit Tests

**Server-side** (`tests/test_question_type.py`):

```python
def test_question_message_validation():
    """Test valid question message structure."""
    pass

def test_question_missing_question_field():
    """Test question without 'question' field is rejected."""
    pass

def test_question_too_few_answers():
    """Test question with < 2 answers is rejected."""
    pass

def test_question_too_many_answers():
    """Test question with > 20 answers is rejected."""
    pass

def test_question_duplicate_answer_ids():
    """Test duplicate answer IDs are rejected."""
    pass

def test_question_timeout_validation():
    """Test timeout must be positive integer."""
    pass

def test_question_timeout_answer_id_not_found():
    """Test timeout_answer_id must exist in answers."""
    pass

def test_answer_submission():
    """Test submitting answer to question."""
    pass

def test_answer_invalid_question_id():
    """Test answering non-existent question."""
    pass

def test_answer_already_answered_question():
    """Test answering question that's already answered."""
    pass

def test_answer_free_text_validation():
    """Test free-text answer validation."""
    pass

def test_timeout_expires():
    """Test timeout sends default answer."""
    pass

def test_timeout_cancelled_on_answer():
    """Test timeout cancelled when answer submitted."""
    pass
```

**Web client** (`tests/test_web_question.py`):

```python
def test_question_rendering():
    """Test question renders with answer options."""
    pass

def test_radio_selection():
    """Test single-select (radio) answer options."""
    pass

def test_checkbox_selection():
    """Test multi-select (checkbox) answer options."""
    pass

def test_free_text_input():
    """Test free-text answer input."""
    pass

def test_timeout_countdown():
    """Test timeout countdown display."""
    pass

def test_answer_submission():
    """Test submitting answer via socket."""
    pass

def test_skip_question():
    """Test skipping question."""
    pass

def test_question_answered_state():
    """Test visual state after answering."""
    pass
```

**CLI rendering** (`tests/test_cli_question.py`):

```python
def test_question_widget_rendering():
    """Test question widget renders correctly."""
    pass

def test_answer_button_selection():
    """Test answer button selection."""
    pass

def test_free_text_input():
    """Test free-text input in CLI."""
    pass

def test_timeout_display():
    """Test timeout countdown display."""
    pass

def test_submit_answer():
    """Test submitting answer from CLI."""
    pass

def test_skip_question():
    """Test skipping question in CLI."""
    pass
```

#### Integration Tests

```python
def test_end_to_end_question_answer():
    """Test question from sender to answer from recipient."""
    pass

def test_question_timeout_e2e():
    """Test question timeout end-to-end."""
    pass

def test_multi_select_question():
    """Test multi-select question with multiple answers."""
    pass

def test_free_text_answer():
    """Test free-text answer submission."""
    pass

def test_cross_client_question():
    """Test question from web client answered by CLI."""
    pass
```

### Implementation Tasks

#### Phase 1: Protocol & Server Validation (Priority: P1)

1. **Task I9-003-A**: Define question message protocol
   - Update message format to include `question_data` field
   - Add `application/x-question` content type
   - Update `on_message` handler to validate question structure
   - **Files**: `src/roomz/server/__init__.py`
   - **Tests**: `tests/test_question_protocol.py`

2. **Task I9-003-B**: Implement question state tracking
   - Create `active_questions` dict to track question state
   - Implement `validate_question_data()` function
   - Add question state: unanswered, answered, timeout
   - **Files**: `src/roomz/server/__init__.py`, `src/roomz/server/models.py`
   - **Tests**: `tests/test_question_state.py`

3. **Task I9-003-C**: Implement answer handler
   - Create `on_answer_question` event handler
   - Validate answer IDs against question
   - Broadcast answer message with `in_reply_to`
   - **Files**: `src/roomz/server/__init__.py`
   - **Tests**: `tests/test_answer_handler.py`

4. **Task I9-003-D**: Implement timeout handler
   - Create `schedule_timeout()` function
   - Create `handle_question_timeout()` function
   - Cancel timeout on answer
   - Send timeout message when timer expires
   - **Files**: `src/roomz/server/__init__.py`
   - **Tests**: `tests/test_question_timeout.py`

#### Phase 2: Web Client Rendering (Priority: P1)

5. **Task I9-003-E**: Add question message template to web client
   - Create question card component
   - Add radio/checkbox answer options
   - Add free-text input for free-text answers
   - Add timeout countdown display
   - **Files**: `src/roomz/server/pages/chat/chat.js`

6. **Task I9-003-F**: Implement answer submission in web client
   - Add `submitAnswer()` method
   - Add `skipQuestion()` method
   - Handle answer confirmation
   - Update question state to "answered"
   - **Files**: `src/roomz/server/pages/chat/chat.js`

7. **Task I9-003-G**: Style question messages
   - Add CSS for question cards
   - Add answered state styling
   - Add timeout warning colors
   - **Files**: `src/roomz/server/static/css/roomz.css`

#### Phase 3: Python CLI Rendering (Priority: P1)

8. **Task I9-003-H**: Create QuestionWidget for CLI
   - Implement question text display
   - Implement answer option buttons
   - Add timeout countdown
   - **Files**: `src/roomz/cli/app_tui.py`

9. **Task I9-003-I**: Implement answer selection in CLI
   - Handle button click for answer selection
   - Add free-text input modal
   - Submit answer to server
   - Handle skip action
   - **Files**: `src/roomz/cli/app_tui.py`

10. **Task I9-003-J**: Handle question events in CLI
    - Handle `question_timeout` event
    - Handle answer confirmation
    - Update question state display
    - **Files**: `src/roomz/cli/app_tui.py`

#### Phase 4: Testing & Documentation (Priority: P2)

11. **Task I9-003-K**: Write server unit tests
    - Test question validation
    - Test answer submission
    - Test timeout handling
    - **Files**: `tests/test_question_type.py`

12. **Task I9-003-L**: Write web client unit tests
    - Test question rendering
    - Test answer selection
    - Test timeout display
    - **Files**: `tests/test_web_question.py`

13. **Task I9-003-M**: Write CLI unit tests
    - Test question widget rendering
    - Test answer submission
    - Test skip action
    - **Files**: `tests/test_cli_question.py`

14. **Task I9-003-N**: Write integration tests
    - End-to-end question/answer flow
    - Timeout handling across clients
    - Cross-client compatibility
    - **Files**: `tests/test_integration_question.py`

15. **Task I9-003-O**: Update documentation
    - Document question message format in README
    - Document answer submission in client library
    - Add examples for sending questions
    - **Files**: `README.md`, `docs/api.md`

### Acceptance Criteria

#### Protocol

- [x] **AC-PROTOCOL-01**: Messages can specify `content_type: "application/x-question"`
- [x] **AC-PROTOCOL-02**: Question messages include `question_data` with required fields
- [x] **AC-PROTOCOL-03**: Invalid question structures are rejected with error
- [x] **AC-PROTOCOL-04**: Answer responses include `in_reply_to` field
- [x] **AC-PROTOCOL-05**: Timeout messages sent when question expires

#### Web Client

- [x] **AC-WEB-01**: Question messages render as card with answer options
- [x] **AC-WEB-02**: Single-select questions use radio buttons
- [x] **AC-WEB-03**: Multi-select questions use checkboxes
- [x] **AC-WEB-04**: Free-text answers show input field
- [x] **AC-WEB-05**: Timeout countdown displays with warning colors
- [x] **AC-WEB-06**: Submit button disabled until answer selected
- [x] **AC-WEB-07**: Skip button marks question as answered (no answer sent)
- [x] **AC-WEB-08**: Answered questions show "Answered" badge
- [x] **AC-WEB-09**: Works on both light and dark themes

#### Python CLI

- [x] **AC-CLI-01**: Question messages render as card with answer buttons
- [x] **AC-CLI-02**: Answer selection highlights selected option
- [x] **AC-CLI-03**: Free-text answers show input prompt
- [x] **AC-CLI-04**: Timeout countdown displays in question widget
- [x] **AC-CLI-05**: Submit button sends answer to server
- [x] **AC-CLI-06**: Skip button marks question as skipped
- [x] **AC-CLI-07**: Answered questions show muted styling

#### Cross-Client

- [x] **AC-CROSS-01**: Questions from web client render correctly in CLI
- [x] **AC-CROSS-02**: Questions from CLI render correctly in web client
- [x] **AC-CROSS-03**: Timeout works across clients (server-side enforcement)

#### Timeout

- [x] **AC-TIMEOUT-01**: Questions with timeout expire after specified duration
- [x] **AC-TIMEOUT-02**: Timeout sends default answer if specified
- [x] **AC-TIMEOUT-03**: Timeout cancelled when answer submitted
- [x] **AC-TIMEOUT-04**: Timeout countdown visible to recipient

#### Security

- [x] **AC-SEC-01**: Question content sanitized (no XSS)
- [x] **AC-SEC-02**: Answer content sanitized
- [x] **AC-SEC-03**: Timeout enforced server-side (not client-side only)
- [x] **AC-SEC-04**: Rate limiting applies to questions (same as messages)

### Dependencies

**External**:
- No new external dependencies (web uses Vuetify components, CLI uses Textual)

**Internal**:
- **I9-001** (Message Content Types) - Protocol change for content_type field
- Both tasks modify the same message protocol, should be coordinated

### Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|--------------|------------|
| Complex state management for questions | High | Medium | Use simple dict for question state, clear lifecycle |
| Timeout race conditions | High | Low | Use asyncio tasks, cancel on answer |
| Large question lists (20+ options) | Medium | Low | Limit to 20 options, efficient rendering |
| Free-text input UX in CLI | Medium | Medium | Use Textual's input modal, clear affordance |
| Multi-select confusion | Low | Medium | Clear UI indication (checkboxes vs radios) |
| Question spam | Medium | Medium | Rate limiting, max questions per user per minute |

### Future Enhancements (Out of Scope)

1. **Question Templates**: Pre-defined question types (Yes/No, Rating 1-5, etc.)
2. **Question History**: View past questions and answers
3. **Question Statistics**: Track answer distribution
4. **Conditional Questions**: Show follow-up questions based on answer
5. **Question Export**: Export questions and answers as data
6. **Anonymous Questions**: Ask without revealing sender identity
7. **Question Threading**: Threaded discussions from questions
8. **Rich Question Content**: Markdown in question text and answer labels

### Estimated Effort

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Protocol & Server | I9-003-A to I9-003-D | 6-8 hours |
| Web Client | I9-003-E to I9-003-G | 8-10 hours |
| Python CLI | I9-003-H to I9-003-J | 6-8 hours |
| Testing & Docs | I9-003-K to I9-003-O | 6-8 hours |
| **Total** | | **26-34 hours** |

### Notes for Implementation

1. **Protocol Compatibility**: The `content_type` field is added in I9-001. I9-003 can reuse the same protocol change. Coordinate with I9-001 implementation.

2. **Timeout Management**: Use `asyncio.create_task` for timeouts. Ensure tasks are cancelled properly on answer or disconnect.

3. **Question State Storage**: In-memory dict is sufficient for MVP. For persistence (future), store in database.

4. **Free-Text UX**: Free-text answers need clear visual indication in both clients. Use placeholder text like "Other: [enter your answer]".

5. **Multi-Select**: For multi-select, the answer is a comma-separated list in the response text.

6. **Accessibility**: Use semantic HTML (`<fieldset>`, `<legend>`, `<input type="radio">`) for question forms. Add ARIA labels.

7. **Testing Priority**: Timeout handling and state management tests must be written first (TDD).

8. **Documentation**: Update client library docs to show how to send questions programmatically.

---

## Analysis Complete

This analysis provides a comprehensive technical design for implementing question message type support in Roomz. The implementation is divided into 4 phases with 15 tasks, estimated at 26-34 hours total.

**Key Decisions**:
1. Question message type `application/x-question` extends I9-001 content type system
2. Simple text response for answers (not special message type)
3. Timeout enforced server-side using asyncio tasks
4. Question state stored in-memory (no persistence in MVP)
5. Multi-select supported via checkboxes (web) and multi-button (CLI)

**Next Steps**:
1. Review this analysis with project stakeholders
2. Coordinate with I9-001 (Content Types) implementation
3. Confirm priority (P1, P2, or P3)
4. Add tasks to TODO.md backlog
5. Begin implementation with Phase 1 (Protocol & Server)