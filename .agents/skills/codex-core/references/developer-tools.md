# Developer tools

`BaseCheckRunner` reads `[tool.codex-check]` from the consuming project's `pyproject.toml` and provides `main()`, `run_ci()`, and individual checks. Its default quality command is pre-commit, type command is mypy, and security command is pip-audit; the consuming project must install and configure those tools. A minimal launcher is:

```python
from pathlib import Path
from codex_core.dev.check_runner import BaseCheckRunner

if __name__ == "__main__":
    BaseCheckRunner(Path(__file__).resolve().parents[2]).main()
```

`ProjectTreeGenerator(root).generate(target_dir, output)` writes a text tree; supply a trusted target directory and output path. `StaticCompiler` in `codex_core.dev.static_compiler` compiles configured CSS/JS bundles. Check the compiler's current methods and configuration format in its docstrings before wiring it into a build. These are opt-in project tools, not import-time behavior.
