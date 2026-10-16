# Storefront text keys

This Django adapter owns interface text, not domain logic or product translations.
Register `web.localization.apps.LocalizationConfig` and use Django's language
middleware and language configuration in the web application.

```django
{% load shop_i18n %}
<h1>{% text 'home.hero.title' %}</h1>
<p>{% text 'common.greeting' name=customer_name %}</p>
```

`messages/de.json` maps stable semantic keys to the German source text. Another
language can be added as `messages/ru.json`, containing a translated subset with
the same keys and named placeholders. Compile catalogs after changes:

```console
python tools/compile_shop_messages.py
```

The command produces standard Django `locale/<language>/LC_MESSAGES/django.po`
and `.mo` catalogs without an external GNU gettext installation. Restart the
application after compiling: Django and the source fallback cache catalogs.
JSON catalogs are the source of truth; generated PO/MO files must not be edited
instead. Standard Django gettext selects translations using the active language.
Absent translations fall back to German; absent keys are visible as `[key]`.

Text is plain text, including interpolated values. Template output is escaped by
Django. Do not add `safe`, HTML strings, or disable autoescaping to render catalog
messages. Keep links and markup in templates and translate their text separately.
Use named placeholders (`{name}`) so translations can change word order. Domain
values, product names and customer content remain distinct from interface keys.

The initial API supports singular interface messages. Count-dependent prose must
receive a dedicated plural-aware extension using Django `ngettext`; do not invent
plural rules by concatenating translated fragments.
