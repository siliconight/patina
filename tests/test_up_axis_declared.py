"""Which way is up is read off the file when the file says, not guessed (0.24.0).

`slots.detect_up_axis` took the axis with the SMALLEST extent as up, because
"a building is wide and shallow". Deli Counter 0.174.0's rowhome Empties are
not: 6.3 m wide, 6.8-10.1 m tall, 12.3 m deep, so up read as X. Every
height-dependent pass then ran on the wrong axis. The walker saw it in cold
run 9147's frames: curbs, base courses and gutters standing out of the
walls, every `ground_edge` and `wall_base` anchor of an Empty on its centre
line at heights from 0 to 10 m. The three real buildings in the same level
read Y and were dressed correctly.

Blender's glTF exporter writes +Y up unless told otherwise, and Deli Counter
never tells it otherwise. So a file that says Blender wrote it is Y-up, and
Patina's own output carries the axis it was given forward. Only a file that
says neither -- the legacy hand-made fixture -- is still guessed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from patina import gltf_io, slots

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
EMPTY = REPO.parent / "deli_counter" / "build" / "gs_empty_rowhome_f.glb"
needs_empty = pytest.mark.skipif(not EMPTY.is_file(),
                                 reason="no Deli Counter build beside this repo")


def _loaded(path) -> "gltf_io.Scene":
    sc = gltf_io.load_glb(str(path))
    sc.bake_visual_transforms()
    return sc


@needs_empty
def test_a_narrow_tall_blender_export_reads_y_up():
    """FAILS ON 0.23.0, which answered X for this file."""
    sc = _loaded(EMPTY)
    assert sc.up_axis_hint == 1
    assert slots.detect_up_axis(sc) == 1


@needs_empty
def test_the_guess_alone_gets_this_building_wrong():
    """The control: strip the declaration and the extents guess answers X --
    the defect, kept visible so nobody restores the guess as the rule."""
    sc = _loaded(EMPTY)
    sc.up_axis_hint = None
    assert slots.detect_up_axis(sc) == 0


@needs_empty
def test_patina_s_own_output_carries_the_axis_forward(tmp_path):
    sc = _loaded(EMPTY)
    out = tmp_path / "x.patina.glb"
    gltf_io.save_glb(sc, str(out))
    again = gltf_io.load_glb(str(out))
    assert again.up_axis_hint == 1


def test_a_file_that_says_nothing_is_still_guessed():
    """The legacy Z-up fixture (`tests/make_fixture.py`, generator
    `DeliCounter-fixture`) declares nothing and is wide, so the guess holds."""
    sc = _loaded(REPO / "examples" / "shell.glb")
    assert sc.up_axis_hint is None
    assert slots.detect_up_axis(sc) == 2


@needs_empty
def test_an_empty_s_ground_anchors_stand_on_the_ground(tmp_path):
    """End to end, the command Level Factory runs for an Empty's dressing
    (recorded in cold run 9147's job): every ground-edge and wall-base anchor
    at the foot of a wall, spread along it, not stacked up its centre line."""
    out = tmp_path / "gs_empty_rowhome_f.patina.glb"
    r = subprocess.run([sys.executable, "-m", "patina.cli", str(EMPTY),
                        "--mode", "vertex-color", "--out", str(out),
                        "--theme", "default", "--dressing", "--anchors", "--gutters"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    d = json.loads((tmp_path / "gs_empty_rowhome_f.patina.dressing.json").read_text(encoding="utf-8"))
    assert d["space"] == "spec/Blender Z-up raw coords"      # z is height here
    ground = [o for o in d["orders"] if o["anchor_kind"] in ("ground_edge", "wall_base")]
    assert ground, "no ground anchors at all -- not the same as correct ones"
    heights = {round(o["pos"][2], 2) for o in ground}
    assert max(heights) <= 0.05 and min(heights) >= -0.35, sorted(heights)
    assert len({round(o["pos"][0], 1) for o in ground}) > 2
