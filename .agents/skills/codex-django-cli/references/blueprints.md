# Blueprint ownership and integration

`codex_django_cli.engine.CLIEngine` reads templates from the installed package's `blueprints` directory. `render_template(name, context)` renders one Jinja template; `scaffold(blueprint_name, target_dir, context, overwrite=False)` walks a subtree. When both `name` and `name.j2` exist, the rendered `.j2` source wins. Existing destination files are skipped unless overwrite is true.

The CLI command handlers build context and choose target paths. Inspect `commands/init.py`, `commands/install.py`, `commands/repo.py`, `commands/deploy.py`, or `commands/quality.py` before calling engine methods directly. A direct engine call must provide the context expected by that blueprint.

Generated Django views and services are application-owned output. The runtime library's public contracts belong to `codex-django`, whose installed version and skill should be checked separately. Keep local business rules in the project, and keep reusable generator changes in the CLI source package.
