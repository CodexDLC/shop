import shutil
import subprocess
from pathlib import Path

import pytest


def test_tabs_units_and_size_selection_contract():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for PDP controls')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, str(root / 'tests/js/product-information.cjs'),
         str(root / 'src/web/static/storefront/product-information.js')],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
