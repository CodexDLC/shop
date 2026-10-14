# Settings

`BaseCommonSettings` extends Pydantic Settings. It supplies `debug`, Redis connection fields, `redis_url`, `is_production`, and `is_development`. It does not select an `.env` file; a consuming application must decide if and where to load one.

```python
from codex_core.settings.base import BaseCommonSettings

class AppSettings(BaseCommonSettings):
    service_name: str = "example"

settings = AppSettings(debug=False, redis_password="a/b")
assert settings.is_production
assert settings.redis_url == "redis://:a%2Fb@localhost:6379"
```

Environment variables may override fields under Pydantic Settings rules. The default `debug=True` means callers must explicitly configure production behavior. `redis_url` percent-encodes the password, but it is still a credential-bearing string; do not log it. Applications that use an `.env` file should define their own `model_config` with an application-controlled path.
