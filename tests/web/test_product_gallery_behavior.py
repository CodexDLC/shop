import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize('script,source', [
    ('product-gallery.cjs', 'product-gallery.js'),
    ('catalog-gallery-selection.cjs', 'catalog-selection.js'),
])
def test_gallery_interaction_contract(script, source):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for gallery interaction checks')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, str(root / 'tests/js' / script), str(root / 'src/web/static/storefront' / source)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
