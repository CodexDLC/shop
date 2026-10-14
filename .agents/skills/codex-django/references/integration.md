# Integration and source discovery

Use the consuming project's Python environment. `importlib.metadata.version("codex-django")` identifies the installed distribution; `importlib.util.find_spec("codex_django").submodule_search_locations` locates its package without booting Django. Read modules as files when Django has not been configured. Many model imports require the app registry.

The runtime package is `codex-django`, import root `codex_django`. Scaffolding belongs to the separate `codex-django-cli` distribution; the `cli` extra is optional. The agent installer lives in the runtime package and needs neither the CLI extra nor Django setup.

## Project wiring

- Add the specific Django apps the integration needs, following their `apps.py`. Do not enable every optional module to obtain one mixin.
- Cabinet: `codex_django.cabinet`; its label is `codex_cabinet`. Include the cabinet context processor in the project's template engine. See [cabinet-shell](cabinet-shell.md) for routes, namespace and access.
- Messaging uses `codex_django.messaging` and its templates. Event registration is project wiring; `AppConfig.ready()` does not discover every project handler automatically.
- Tracking has concrete models/migrations. Abstract library models in other modules require project subclasses and project migrations.
- Optional `admin`/Unfold support does not register project models or automatically convert a cabinet into Django admin.

Inspect an existing project setup before adding settings or replacing view classes. A fresh app installation is different from extending an already integrated site.

## Agent setup

Run from the environment containing the desired library version:

```text
python -m codex_django.agent_skills install --project /path/to/project
python -m codex_django.agent_skills status --project /path/to/project
python -m codex_django.agent_skills update --project /path/to/project
python -m codex_django.agent_skills delete --project /path/to/project
```

The target is project-local `.agents/skills/codex-django/`, with a managed reference in the project's root `AGENTS.md`. Installation is optional for normal Python use. Refresh the skill after upgrading the package; `update` refreshes managed library instructions, not project-specific skills. `delete` removes the managed instructions, not the Python package.

## Where to verify

- `cabinet/__init__.py`, `booking/__init__.py`, `messaging/__init__.py`: public integration exports, including lazy model exports.
- A module's `apps.py`, `urls.py`, `context_processors.py`: actual discovery and wiring requirements.
- `cabinet/templates/`, `messaging/templates/`, `showcase/`: shipped templates and examples. Showcase uses mocks; it is not a reference for production access control.
