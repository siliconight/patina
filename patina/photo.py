"""Photo projection (v0.16): rectified photo regions as texture sources.

The tile importers (``byo`` mode, ``--override key=photo.jpg``) assume the
photo *is* the surface: they centre-crop a square and crush it. Real reference
photos aren't like that — one phone shot of a storefront contains the sign,
the wall, and a poster, all photographed at an angle. This module is the
missing front-end: mark the four corners of each region you want, and Patina
perspective-rectifies the quad, crushes it to a period-correct texture
(box-downscale, posterize, optional family lock), optionally makes it
seamlessly tileable, and writes a set that drops straight into the existing
``byo`` / override machinery.

Honest-seams position: picking *which* rectangle of the world becomes a
texture is irreducible human judgment, so the corners live in a savable JSON
spec (same philosophy as the overrides bash session). Everything after the
corners is mechanical and automated here.

Spec file::

    {
      "source": "ref/pizza_front.jpg",
      "out": "./photo_textures",
      "posterize": 16,
      "family": {"extract": 8},              // or {"path": "fam.json"}, or omit
      "regions": [
        {"key": "wall",
         "corners": [[80,410],[690,430],[688,980],[75,965]],   // TL,TR,BR,BL
         "size": [128,128], "tile": "both"},
        {"key": "sign_pizza",
         "corners": [[120,60],[980,90],[975,360],[115,330]],
         "size": [256,128]}
      ]
    }

Output per region is ``<out>/<key>.png``, plus ``<out>/family.json`` when
extraction is requested, ``<out>/overrides.json`` ready for ``--overrides``
(images marked ``"process": false`` — they are already crushed; the square
centre-crop in ``import_tile`` would destroy non-square signs), and
``<out>/photo_manifest.json`` recording the source hash, the spec, and the
tool version.

Determinism: output is a pure function of the source file bytes and the spec.
No randomness is used anywhere in this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image

from . import families
from .palette import posterize as _posterize
from .version import __version__

_VALID_TILE = ("none", "x", "y", "both")
# Fraction of the tile blended across each wrapped seam.
_SEAM_BAND = 0.12


# --------------------------------------------------------------------------
# rectify
# --------------------------------------------------------------------------

def rectify(im: Image.Image, corners: list[list[float]], size: tuple[int, int],
            supersample: int = 2) -> Image.Image:
    """Perspective-rectify the quad ``corners`` (TL, TR, BR, BL in source
    pixels) to a ``size`` rectangle.

    Sampling happens at ``supersample`` x the target size, then box-filters
    down — the downscale is part of the period look, and box filtering over a
    supersampled rectification avoids shimmer that direct nearest sampling
    would bake in.
    """
    if len(corners) != 4 or any(len(c) != 2 for c in corners):
        raise ValueError("corners must be four [x, y] pairs (TL, TR, BR, BL)")
    w, h = int(size[0]), int(size[1])
    if w < 2 or h < 2:
        raise ValueError("region size must be at least 2x2")
    ss = max(1, int(supersample))
    tl, tr, br, bl = corners
    # PIL QUAD wants NW, SW, SE, NE.
    quad = (tl[0], tl[1], bl[0], bl[1], br[0], br[1], tr[0], tr[1])
    out = im.convert("RGB").transform(
        (w * ss, h * ss), Image.QUAD, data=quad, resample=Image.BICUBIC)
    if ss > 1:
        out = out.resize((w, h), Image.BOX)
    return out


# --------------------------------------------------------------------------
# seamless tiling
# --------------------------------------------------------------------------

def make_tileable(arr: np.ndarray, axes: str) -> np.ndarray:
    """Offset-wrap + cross-blend a float RGB array so it tiles along ``axes``
    (``"x"``, ``"y"`` or ``"both"``). Deterministic; no cloning or synthesis —
    just the classic half-offset with a linear blend band across the seam."""
    if axes == "none":
        return arr
    out = arr
    if axes in ("x", "both"):
        out = _blend_axis(out, axis=1)
    if axes in ("y", "both"):
        out = _blend_axis(out, axis=0)
    return out


def _blend_axis(arr: np.ndarray, axis: int) -> np.ndarray:
    n = arr.shape[axis]
    band = max(2, int(n * _SEAM_BAND))
    rolled = np.roll(arr, n // 2, axis=axis)
    # Ramp 0->1 over the band centred on the (now mid-image) seam.
    t = np.zeros(n, np.float32)
    lo = n // 2 - band // 2
    t[lo:lo + band] = np.linspace(0.0, 1.0, band, dtype=np.float32)
    t[lo + band:] = 1.0
    # Blend rolled into itself shifted by the band ramp: classic seam cover.
    shape = [1, 1, 1]
    shape[axis] = n
    t = t.reshape(shape)
    covered = rolled * (1.0 - t) + np.roll(rolled, band, axis=axis) * t
    return np.roll(covered, -(n // 2), axis=axis)


# --------------------------------------------------------------------------
# spec pass
# --------------------------------------------------------------------------

def run_spec(spec_path: str) -> dict:
    """Execute a photo spec. Returns the manifest dict (also written to
    ``<out>/photo_manifest.json``)."""
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    base = os.path.dirname(os.path.abspath(spec_path))

    src = spec.get("source")
    if not src:
        raise ValueError("spec needs a 'source' image path")
    src_abs = src if os.path.isabs(src) else os.path.join(base, src)
    out_dir = spec.get("out", "./photo_textures")
    out_abs = out_dir if os.path.isabs(out_dir) else os.path.join(base, out_dir)
    os.makedirs(out_abs, exist_ok=True)

    regions = spec.get("regions") or []
    if not regions:
        raise ValueError("spec has no regions")
    default_poster = int(spec.get("posterize", 16))
    supersample = int(spec.get("supersample", 2))

    with open(src_abs, "rb") as f:
        src_bytes = f.read()
    src_sha = hashlib.sha256(src_bytes).hexdigest()

    family = _resolve_family(spec.get("family"), src_abs, base, out_abs)

    im = Image.open(src_abs)
    im.load()

    written: list[dict] = []
    overrides: dict[str, dict] = {}
    for region in regions:
        key = region.get("key")
        if not key:
            raise ValueError("every region needs a 'key'")
        size = tuple(region.get("size", [128, 128]))
        tile = region.get("tile", "none")
        if tile not in _VALID_TILE:
            raise ValueError(
                f"region '{key}': tile must be one of {_VALID_TILE}")
        rect = rectify(im, region["corners"], size, supersample)
        arr = np.asarray(rect, np.float32) / 255.0
        arr = make_tileable(arr, tile)
        arr = _posterize(arr, int(region.get("posterize", default_poster)))
        if family is not None and region.get("family_lock", True):
            arr = families.quantize(arr, family)
        png_name = f"{key}.png"
        Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8),
                        "RGB").save(os.path.join(out_abs, png_name))
        overrides[key] = {"image": png_name, "process": False}
        written.append({"key": key, "file": png_name, "size": list(size),
                        "tile": tile,
                        "region": {k: v for k, v in region.items()}})

    with open(os.path.join(out_abs, "overrides.json"), "w",
              encoding="utf-8") as f:
        json.dump(overrides, f, indent=2)

    manifest = {
        "patina_photo_version": __version__,
        "source": src,
        "source_sha256": src_sha,
        "posterize": default_poster,
        "supersample": supersample,
        "family": (spec.get("family") or None),
        "regions": written,
    }
    with open(os.path.join(out_abs, "photo_manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def _resolve_family(family_spec, src_abs: str, base: str, out_abs: str):
    """Resolve the optional family block: extract from the source photo, or
    load an existing family file. Extracted families are saved next to the
    textures so the run is reproducible without re-extraction."""
    if not family_spec:
        return None
    if "path" in family_spec:
        p = family_spec["path"]
        return families.load(p if os.path.isabs(p) else os.path.join(base, p))
    k = int(family_spec.get("extract", 8))
    fam = families.extract(src_abs, k)
    families.save(fam, os.path.join(out_abs, "family.json"))
    return fam


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("usage: patina-photo SPEC.json [SPEC2.json ...]")
        return 0
    for spec_path in argv:
        manifest = run_spec(spec_path)
        keys = ", ".join(r["key"] for r in manifest["regions"])
        print(f"patina-photo: {manifest['source']} -> "
              f"{len(manifest['regions'])} region(s) [{keys}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
