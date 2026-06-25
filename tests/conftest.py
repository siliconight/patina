"""Shared pytest fixtures.

Builds a fresh synthetic Deli-Counter-shaped shell in a temp dir so the offline
tests never depend on a checked-in binary or a real Deli Counter install.
"""

from __future__ import annotations

import pytest

from tests.make_fixture import build


@pytest.fixture()
def shell(tmp_path):
    """Path to a freshly generated shell.glb (+ sibling gameplay.json)."""
    p = tmp_path / "shell.glb"
    build(str(p))
    return str(p)
