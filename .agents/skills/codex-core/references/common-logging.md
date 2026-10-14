# Common helpers and logging

`codex_core.common` exports `normalize_phone`, `normalize_name`, `clean_string`, `transliterate`, and `sanitize_for_sms`. `normalize_phone` returns digits and expands a local leading zero using the supplied country code (`49` by default); it does not validate reachability or E.164 length. `sanitize_for_sms` strips some characters and truncates input; it is not a general HTML, SQL, or shell sanitizer.

For request or task context, `set_log_context(**fields)` merges into the current async context, `get_log_context()` returns a copy, and `clear_log_context()` clears it. Clear context in `finally` at the application boundary:

```python
from codex_core.common import clear_log_context, get_log_context, set_log_context

try:
    set_log_context(request_id="req-7")
    assert get_log_context()["request_id"] == "req-7"
finally:
    clear_log_context()
```

`TaskLogContext` wraps standard-library logging with fixed task fields. `setup_logging` and `setup_universal_logging` require the optional `loguru` extra. `setup_logging` accepts an object implementing `LoggingSettingsProtocol` (`debug`, `log_dir`, `log_level_console`, `log_level_file`, `log_rotation`); `BaseCommonSettings` alone does not provide all those fields. In development it configures console and file sinks; in production it configures JSON stdout. Both setup functions replace root logging handlers and should be called once in application startup, after the application chooses logging policy.
