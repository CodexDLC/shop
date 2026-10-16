import gettext
import importlib.util
import io
import json
from pathlib import Path

from django.template import Context, Engine
from django.utils.translation import override

from web.localization import translate_text


def test_german_source_and_missing_translation_fallback():
    with override("de"):
        assert translate_text("home.hero.title") == "Dein Stil. Deine Underwear."
    with override("ru"):
        assert translate_text("common.shop_name") == "Männermasche"


def test_unknown_key_has_diagnostic_fallback():
    assert translate_text("unknown.example") == "[unknown.example]"


def test_interpolation_remains_escaped_in_templates():
    engine = Engine(libraries={"shop_i18n": "web.localization.templatetags.shop_i18n"})
    template = engine.from_string("{% load shop_i18n %}{% text 'common.greeting' name=name %}")
    assert template.render(Context({"name": '<script>alert("x")</script>'})) == (
        "Hallo &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
    )


def test_compiler_produces_gettext_catalog(tmp_path):
    script = Path(__file__).resolve().parents[2] / "tools/compile_shop_messages.py"
    spec = importlib.util.spec_from_file_location("compile_shop_messages", script)
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    (tmp_path / "messages").mkdir()
    (tmp_path / "messages/de.json").write_text(
        json.dumps({"test.example": "Größe {size}"}), encoding="utf-8"
    )
    paths = compiler.compile_catalogs(tmp_path)
    catalog = gettext.GNUTranslations(io.BytesIO(paths[0].read_bytes()))
    assert catalog.gettext("test.example") == "Größe {size}"
