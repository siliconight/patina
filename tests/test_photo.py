"""Tests for patina.photo — rectification, seams, determinism."""

import json
import os

import numpy as np
import pytest
from PIL import Image

from patina import photo


@pytest.fixture
def storefront(tmp_path):
    """Synthetic angled 'storefront': red quad (sign) and green quad (wall)
    on gray, drawn as perspective-skewed regions of a 400x300 photo."""
    img = np.full((300, 400, 3), 90, np.uint8)
    img[40:110, 60:340] = (200, 40, 40)     # sign band
    img[130:280, 80:320] = (60, 160, 60)    # wall block
    p = tmp_path / "front.png"
    Image.fromarray(img).save(p)
    return p


def _spec(tmp_path, storefront, **extra):
    spec = {
        "source": str(storefront),
        "out": str(tmp_path / "out"),
        "regions": [
            {"key": "sign_test", "corners": [[60, 40], [340, 40],
                                             [340, 110], [60, 110]],
             "size": [128, 64]},
            {"key": "wall", "corners": [[80, 130], [320, 130],
                                        [320, 280], [80, 280]],
             "size": [64, 64], "tile": "both"},
        ],
    }
    spec.update(extra)
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec))
    return p


def test_regions_written_with_size_and_manifest(tmp_path, storefront):
    manifest = photo.run_spec(str(_spec(tmp_path, storefront)))
    out = tmp_path / "out"
    sign = Image.open(out / "sign_test.png")
    assert sign.size == (128, 64)
    wall = Image.open(out / "wall.png")
    assert wall.size == (64, 64)
    assert manifest["source_sha256"]
    assert {r["key"] for r in manifest["regions"]} == {"sign_test", "wall"}
    ov = json.loads((out / "overrides.json").read_text())
    assert ov["wall"] == {"image": "wall.png", "process": False}


def test_rectified_region_holds_source_colour(tmp_path, storefront):
    photo.run_spec(str(_spec(tmp_path, storefront)))
    arr = np.asarray(Image.open(tmp_path / "out" / "sign_test.png"), np.float32)
    center = arr[24:40, 40:88].mean(axis=(0, 1))
    assert center[0] > 150 and center[1] < 90  # red sign, not gray background


def test_tileable_wraps(tmp_path, storefront):
    photo.run_spec(str(_spec(tmp_path, storefront)))
    arr = np.asarray(Image.open(tmp_path / "out" / "wall.png"), np.float32)
    # Wrapped-edge difference should be small after seam treatment.
    edge_x = np.abs(arr[:, 0] - arr[:, -1]).mean()
    edge_y = np.abs(arr[0, :] - arr[-1, :]).mean()
    assert edge_x < 40 and edge_y < 40


def test_posterize_limits_levels(tmp_path, storefront):
    photo.run_spec(str(_spec(tmp_path, storefront, posterize=4)))
    arr = np.asarray(Image.open(tmp_path / "out" / "sign_test.png"))
    assert len(np.unique(arr[..., 0])) <= 4


def test_family_extract_and_lock(tmp_path, storefront):
    spec = _spec(tmp_path, storefront, family={"extract": 4})
    photo.run_spec(str(spec))
    assert (tmp_path / "out" / "family.json").exists()


def test_deterministic(tmp_path, storefront):
    spec = _spec(tmp_path, storefront)
    photo.run_spec(str(spec))
    first = (tmp_path / "out" / "wall.png").read_bytes()
    photo.run_spec(str(spec))
    assert (tmp_path / "out" / "wall.png").read_bytes() == first


def test_bad_tile_axis_rejected(tmp_path, storefront):
    spec = {
        "source": str(storefront), "out": str(tmp_path / "out"),
        "regions": [{"key": "wall", "corners": [[0, 0], [10, 0],
                                                [10, 10], [0, 10]],
                     "tile": "diagonal"}],
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        photo.run_spec(str(p))
