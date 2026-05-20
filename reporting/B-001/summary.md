# Task Summary: Bug B-001 - Fix double-quoting of EMAIL_FROM in ResendEmailSender

## Implementation Details
Fixed a critical bug where the `EMAIL_FROM` environment variable was being sent with literal surrounding quotes to the Resend API, causing `422 Unprocessable Entity` validation errors.

### Changes Made
- **Sanitization**: Updated `ResendEmailSender.__init__` to strip leading and trailing single and double quotes from `os.getenv("EMAIL_FROM")`.
- **Robust Fallback**: Implemented a fallback to `DEFAULT_FROM_ADDRESS` if the sanitized value is empty.
- **DRY Refactor**: Extracted token extraction logic from `ResendEmailSender` and `ConsoleEmailSender` into a new shared utility `src/roomz/server/email/utils.py`.
- **Observability**: Improved error logging in `ResendEmailSender` to capture full exception messages.
- **Clean Code**: Replaced `asyncio.get_event_loop()` with `asyncio.get_running_loop()`.
- **Dependency Management**: Replaced circular `from .. import server` imports with a dedicated module-level logger `logging.getLogger("roomz")`.

## Verification Results
- **Tests**: 5 new test cases in `tests/test_email_integration.py` verifying:
    - Basic quote stripping (`"user@example.com"` -> `user@example.com`)
    - Multiple quote stripping (`""user@example.com""` -> `user@example.com`)
    - Unquoted value preservation
    - Fallback when only quotes are provided
    - Fallback when value is empty
- **Overall Status**: All 53 integration tests passed.
- **Linting**: Passed.

## Requirements Satisfied
- **R103**: Environment variables used for configuration must be sanitized to remove accidental surrounding quotes.
