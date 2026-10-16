import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def page_manifest():
    return json.loads(Path(__file__).with_name('page_manifest.json').read_text(encoding='utf-8'))
