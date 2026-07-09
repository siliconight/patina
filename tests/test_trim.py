"""Trim sheets + dressing manifest: atlas regions cover the sheet, family lock,
anchor->order mapping with collision:none, determinism, and CLI wiring."""

from __future__ import annotations

import io
import json
import os

import numpy as np
from PIL import Image

from patina import anchors, cli, families, trim


def test_build_sheet_regions_tile_the_sheet():
    png, regions = trim.build_sheet(size=128, seed=1999,
                                    family=families.load("delco_faded"))
    assert png[:8].startswith(b"\x89PNG")
    # every declared piece has a region
    assert {r.piece for r in regions} == set(trim.TRIM_PIECES)
    # regions are stacked top-to-bottom, contiguous, covering 0..1 in v
    regions_sorted = sorted(regions, key=lambda r: r.v0)
    assert regions_sorted[0].v0 == 0.0
    assert abs(regions_sorted[-1].v1 - 1.0) < 0.02
    for a, b in zip(regions_sorted, regions_sorted[1:]):
        assert abs(a.v1 - b.v0) < 1e-6           # contiguous, no gaps


def test_trim_sheet_family_locked():
    fam = families.load("delco_faded")
    png, _ = trim.build_sheet(size=96, seed=7, family=fam)
    lib = {tuple(int(x) for x in np.round(c * 255)) for c in fam.palette_rgb()}
    arr = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).reshape(-1, 3)
    seen = {tuple(int(x) for x in c) for c in np.unique(arr, axis=0)}
    assert seen <= lib


def test_trim_sheet_deterministic():
    a, _ = trim.build_sheet(size=64, seed=3, family=families.load("delco_faded"))
    b, _ = trim.build_sheet(size=64, seed=3, family=families.load("delco_faded"))
    assert a == b


def _anchors():
    return [
        anchors.Anchor("roofline", (0, 0, 4.2), (0, 0, 1), 0.6),
        anchors.Anchor("wall_base", (1, 0, 0), (1, 0, 0), 0.8),
        anchors.Anchor("exterior_light", (2, 0, 3), (1, 0, 0), 0.3),
        anchors.Anchor("ground_edge", (3, 0, 0), (0, 0, 1), 0.4),
    ]


def test_dressing_orders_map_anchors_to_trim():
    _, regions = trim.build_sheet(size=64, seed=1, family=None)
    orders = trim.dressing_orders(_anchors(), regions, seed=1)
    by_kind = {o["anchor_kind"]: o for o in orders}
    assert by_kind["roofline"]["trim_piece"] == "roof_edge"
    assert by_kind["roofline"]["cover"] == "edge_strip"
    assert by_kind["wall_base"]["trim_piece"] == "foundation"
    # every order is non-collision and carries a UV region + position
    for o in orders:
        assert o["collision"] == "none"
        assert len(o["uv_region"]) == 4 and len(o["pos"]) == 3


def test_dressing_manifest_shape():
    _, regions = trim.build_sheet(size=64, seed=1, family=None)
    dm = trim.dressing_manifest(_anchors(), regions, seed=1, source="x.glb",
                                sheet_file="x.trim.png",
                                space="spec/Blender Z-up raw coords",
                                building_id="b1")
    assert dm["schema"] == "patina-dressing/1"
    assert dm["trim_sheet"] == "x.trim.png"
    assert dm["building_id"] == "b1"
    assert len(dm["orders"]) == 4
    assert set(dm["trim_regions"]) == set(trim.TRIM_PIECES)


def test_dressing_orders_deterministic():
    _, regions = trim.build_sheet(size=64, seed=1, family=None)
    a = trim.dressing_orders(_anchors(), regions, seed=5)
    b = trim.dressing_orders(_anchors(), regions, seed=5)
    assert a == b


def _run(shell, tmp_path, extra):
    out = str(tmp_path / "o.glb")
    args = cli.build_parser().parse_args(
        [shell, "--mode", "procedural", "--out", out] + extra)
    return cli.run(args), out


def test_cli_trim_sheet_standalone(shell, tmp_path):
    res, _ = _run(shell, tmp_path, ["--theme", "delco_1997_gas_station",
                                    "--trim-sheet"])
    assert os.path.exists(res["trim_sheet"])
    rpath = res["trim_sheet"][:-9] + ".trim.json"
    assert os.path.exists(rpath)
    j = json.load(open(rpath))
    assert set(j["regions"]) == set(trim.TRIM_PIECES)


def test_cli_dressing_needs_anchors(shell, tmp_path):
    res, _ = _run(shell, tmp_path, ["--theme", "delco_1997_gas_station",
                                    "--anchors", "--dressing"])
    assert res["dressing"]["orders"] > 0
    assert os.path.exists(res["dressing"]["sidecar"])
    dm = json.load(open(res["dressing"]["sidecar"]))
    assert all(o["collision"] == "none" for o in dm["orders"])
