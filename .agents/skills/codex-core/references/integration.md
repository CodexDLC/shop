# Integration and version discovery

Check the installed distribution and module location before using version-specific guidance:

```python
from importlib.metadata import version
from pathlib import Path
import codex_core

print(version("codex-core"))
print(Path(codex_core.__file__).resolve())
```

The source skill payload is available as package resources in `codex_core.agent_skills.resources`; a consumer installation at `.agents/skills/codex-core/` is a managed copy with `.manifest.json`. Do not edit that copy or its manifest to adopt local changes. After upgrading the package, use `python -m codex_core.agent_skills update --project PATH` from the upgraded environment and then `status`. The installer refuses an update if managed files were locally modified; save those edits separately and reapply appropriate application guidance in a project-owned skill. It does not fetch content over the network.
