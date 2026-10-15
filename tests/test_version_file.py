"""`patina.__version__` is the number in VERSION (0.32.0).

The two had drifted: 0.31.0 bumped `VERSION` and not `patina/version.py`, so every manifest and GLB of that
release wrote `generator: "Patina 0.30.0"`. The version is what makes an output traceable to the code that
made it, and a wrong one is worse than none. This fails on 0.31.0's tree.
"""
import pathlib

import patina

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_module_version_is_the_version_file():
    text = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert text.startswith("Patina "), text
    assert patina.__version__ == text.split()[1]
