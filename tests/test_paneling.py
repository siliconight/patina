"""Tests for panel-field orders (v0.17)."""

import math

import pytest

from patina import paneling, trim
from patina.slots import Slot, SlotManifest


def _slot(slot_id="ext_0_N_seg0", facing="N", rot_y=0.0, dims=(2.0, 0.3, 4.2),
          translation=(-15.0, 11.0, 2.1), pivot="center", role="wall"):
    return Slot(slot_id=slot_id, role=role, current_ref="wall_greybox_01",
                facing=facing, translation=translation, rot_y=rot_y,
                dims=dims, pivot=pivot)


def _manifest(slots):
    return SlotManifest(version="1.2.0", building_id="t", theme="greybox",
                        module_library="art/zoo", module_size=2.0,
                        space="spec/Blender Z-up raw coords", slots=slots)


def _regions():
    _, regions = trim.build_sheet(size=64, seed=1999)
    return regions


def test_grid_covers_wall_and_skips_openings():
    m = _manifest([_slot(),
                   _slot(slot_id="ext_0_N_open1", role="doorway")])
    orders = paneling.panel_orders(m, _regions(), seed=1999)
    # 2.0m wide / 1.2 target -> 2 cols; 4.2m tall -> round(3.5) = 4 rows
    assert len(orders) == 8
    assert all(o["cover"] == "panel_field" for o in orders)
    assert all(o["slot_id"] == "ext_0_N_seg0" for o in orders)  # no doorway
    assert all(o["collision"] == "none" for o in orders)


def test_panel_face_offset_and_normal():
    m = _manifest([_slot()])
    o = paneling.panel_orders(m, _regions(), seed=1999)[0]
    # facing N, rot_y 0: normal +Y, face plane at ty + d/2
    assert o["normal"] == [0.0, 1.0, 0.0]
    assert o["pos"][1] == pytest.approx(11.0 + 0.15, abs=1e-3)
    w, h = o["size2"]
    assert w == pytest.approx(1.0 - 0.03, abs=1e-3)
    assert h == pytest.approx(1.05 - 0.03, abs=1e-3)
    assert o["size"] == pytest.approx(w)


def test_rotation_rotates_normal_and_positions():
    m = _manifest([_slot(rot_y=90.0)])
    o = paneling.panel_orders(m, _regions(), seed=1999)[0]
    assert o["normal"] == [-1.0, 0.0, 0.0]


def test_interior_walls_skipped_when_exterior_marked():
    m = _manifest([_slot(),
                   _slot(slot_id="int_0_seg0", facing=None)])
    orders = paneling.panel_orders(m, _regions(), seed=1999)
    assert {o["slot_id"] for o in orders} == {"ext_0_N_seg0"}


def test_deterministic():
    m = _manifest([_slot()])
    a = paneling.panel_orders(m, _regions(), seed=1999)
    b = paneling.panel_orders(m, _regions(), seed=1999)
    assert a == b


def test_manifest_appends_extra_orders():
    regions = _regions()
    m = _manifest([_slot()])
    panels = paneling.panel_orders(m, regions, seed=1999)
    dm = trim.dressing_manifest([], regions, seed=1999, source="t.glb",
                                sheet_file="t.trim.png",
                                space="spec/Blender Z-up raw coords",
                                building_id="t", extra_orders=panels)
    assert len(dm["orders"]) == 8
    assert dm["counts"]["panel_field"] == 8


def test_budget_clamp():
    m = _manifest([_slot(slot_id=f"ext_{i}") for i in range(50)])
    orders = paneling.panel_orders(m, _regions(), seed=1999, max_orders=20)
    assert len(orders) == 20
