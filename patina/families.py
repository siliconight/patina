"""Texture families (v0.5): the limited, shared material library.

The cohesion in Quake 2 wasn't per-texture polish — it was *constraint*. id
built texture *families* (Paul Steed, "The Art of Quake 2"; the TextureBuild
tool assembled them) so every area of a level reused a small, shared palette
and set of materials. Patina generates each surface's colours independently,
so nothing enforces that the brick, the lino and the ceiling belong to the
same world. A **family** makes the palette the unit of reuse and *locks*
every surface to it.

A family is a small ordered list of colours (the "material library") plus an
optional discipline. Binding a family to a run runs a **palette-lock** pass:
every generated tile, every imported photo, and every vertex tint is
quantised to the nearest family colour. The result is literal cohesion — the
whole level shares N colours — and it is the reusable unit *across* levels:
run every shell with the same family and the game reads as one place.

Two ways to get a family:

* **Author it** — a builtin name or a ``family.json`` (``{"name", "colors":
  [hex...], "posterize"?}``) that lives in the project. The saved file is the
  shared library; point every area at it.
* **Extract it** — ``extract(image, k)`` runs deterministic k-means over a
  reference photo / moodboard and returns a k-colour family. This is the
  TextureBuild move: build a coherent set from one source, then lock
  everything to it.

Determinism: extraction is a deterministic function of the image bytes + seed
(fixed k-means++ init and iteration count); quantisation is nearest-colour,
order-independent. A run with **no** family bound skips the pass entirely and
is byte-identical to v0.4.
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from .determinism import rng_for


@dataclass(frozen=True)
class Family:
    name: str
    colors: tuple[str, ...] = ()          # ordered hex library, sorted by luma
    posterize: int | None = None          # optional shared colour-depth discipline
    source: str = "builtin"

    def palette_rgb(self) -> np.ndarray:
        return np.array([_hex(c) for c in self.colors], np.float32)  # (K, 3)


def _hex(s: str) -> tuple[float, float, float]:
    t = s.strip().lstrip("#")
    if len(t) != 6:
        raise ValueError(f"bad family colour {s!r} (want '#rrggbb')")
    return tuple(int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore


def _to_hex(rgb: np.ndarray) -> str:
    r, g, b = (int(round(float(c) * 255)) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _luma(rgb: np.ndarray) -> float:
    return float(0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])


# --------------------------------------------------------------------------- #
# Builtins
# --------------------------------------------------------------------------- #

_BUILTINS: dict[str, dict] = {
    # A faded late-90s Delco palette that harmonises with the
    # delco_1997_gas_station theme: warm greys, oxblood, nicotine cream, teal,
    # tar. Small on purpose — that's the whole point.
    "delco_faded": {
        "colors": [
            "#20201d", "#3a3833", "#55524a", "#726d61", "#8f8877",
            "#b7ad97", "#6e2a24", "#245055", "#a98a52", "#c9c3ad",
        ],
        "posterize": 16,
    },
}


def builtin_names() -> list[str]:
    return sorted(_BUILTINS)


def _make(name: str, colors: list[str], posterize: int | None,
          source: str) -> Family:
    if not colors:
        raise ValueError(f"family {name!r}: needs at least one colour")
    rgb = [np.array(_hex(c), np.float32) for c in colors]
    order = sorted(range(len(rgb)), key=lambda i: _luma(rgb[i]))
    ordered = tuple(_to_hex(rgb[i]) for i in order)      # canonical: luma-sorted
    if posterize is not None and not (2 <= posterize <= 256):
        raise ValueError(f"family {name!r}: posterize must be 2..256")
    return Family(name=name, colors=ordered, posterize=posterize, source=source)


def load(name_or_path: str) -> Family:
    """Builtin family name, or a path to a ``family.json``."""
    if name_or_path in _BUILTINS:
        b = _BUILTINS[name_or_path]
        return _make(name_or_path, list(b["colors"]), b.get("posterize"), "builtin")
    if os.path.exists(name_or_path):
        with open(name_or_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict) or "colors" not in raw:
            raise ValueError(f"{name_or_path}: family file needs a 'colors' list")
        name = raw.get("name") or os.path.splitext(os.path.basename(name_or_path))[0]
        return _make(name, list(raw["colors"]), raw.get("posterize"),
                     os.path.abspath(name_or_path))
    raise ValueError(
        f"unknown family {name_or_path!r} (builtins: {', '.join(builtin_names())}, "
        "or a path to a family .json)")


def save(family: Family, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"name": family.name, "colors": list(family.colors),
                   **({"posterize": family.posterize}
                      if family.posterize is not None else {})},
                  fh, indent=2)
        fh.write("\n")


# --------------------------------------------------------------------------- #
# Extraction (the "build a family from a source" move)
# --------------------------------------------------------------------------- #

def extract(image_path: str, k: int = 8, *, seed: int = 1999,
            name: str | None = None, sample: int = 128) -> Family:
    """Derive a k-colour family from a reference image (deterministic k-means).

    The image is downsampled to ``sample`` px on its long edge for speed;
    k-means++ init and the iteration count are seeded, so the same file + seed
    always yields the same library. Empty clusters are re-seeded to the
    farthest pixel (still deterministic). Returned colours are luma-sorted.
    """
    if not (1 <= k <= 64):
        raise ValueError("family k must be 1..64")
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        scale = sample / max(w, h)
        if scale < 1.0:
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                           Image.BOX)
        data = (np.asarray(im, np.float32) / 255.0).reshape(-1, 3)

    rng = rng_for(seed, "family", "extract", os.path.basename(image_path), str(k))
    centers = _kpp_init(data, k, rng)
    for _ in range(16):
        d = ((data[:, None, :] - centers[None, :, :]) ** 2).sum(-1)   # (N, K)
        labels = d.argmin(1)
        new = centers.copy()
        for j in range(k):
            m = labels == j
            if m.any():
                new[j] = data[m].mean(0)
            else:
                # farthest pixel from its assigned centre -> re-seed (deterministic)
                new[j] = data[d.min(1).argmax()]
        if np.allclose(new, centers, atol=1e-4):
            centers = new
            break
        centers = new
    colors = [_to_hex(c) for c in centers]
    return _make(name or f"extracted_{os.path.splitext(os.path.basename(image_path))[0]}",
                 colors, None, os.path.abspath(image_path))


def _kpp_init(data: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    n = data.shape[0]
    centers = [data[int(rng.integers(0, n))]]
    for _ in range(1, k):
        d = np.min(((data[:, None, :] - np.array(centers)[None, :, :]) ** 2).sum(-1), 1)
        total = d.sum()
        if total <= 0:
            centers.append(data[int(rng.integers(0, n))])
            continue
        # sample proportional to squared distance, deterministically
        r = float(rng.random()) * total
        idx = int(np.searchsorted(np.cumsum(d), r))
        centers.append(data[min(idx, n - 1)])
    return np.array(centers, np.float32)


# --------------------------------------------------------------------------- #
# The palette-lock pass
# --------------------------------------------------------------------------- #

def quantize(arr: np.ndarray, family: Family) -> np.ndarray:
    """Snap an (..., 3) float array to the nearest family colours."""
    pal = family.palette_rgb()
    flat = arr.reshape(-1, 3)
    d = ((flat[:, None, :] - pal[None, :, :]) ** 2).sum(-1)
    return pal[d.argmin(1)].reshape(arr.shape)


def lock_tint(rgb: tuple[float, float, float], family: Family) \
        -> tuple[float, float, float]:
    """Snap one vertex-tint colour to the family (so tints match the tiles)."""
    q = quantize(np.array([[rgb]], np.float32), family)[0, 0]
    return (float(q[0]), float(q[1]), float(q[2]))


def lock_tiles(tiles: dict[str, bytes], family: Family) -> dict[str, bytes]:
    """Quantise every tile PNG to the family library, in place; return it.

    Uniform over procedural, byo and override-image tiles — whatever produced
    the bytes, the surface ends up sharing the family's colours.
    """
    for key, data in tiles.items():
        with Image.open(io.BytesIO(data)) as im:
            mode = im.mode
            rgb = np.asarray(im.convert("RGB"), np.float32) / 255.0
        q = (quantize(rgb, family) * 255).astype(np.uint8)
        out = Image.fromarray(q, "RGB")
        if mode in ("RGBA", "LA", "P"):     # keep alpha if the source had it
            with Image.open(io.BytesIO(data)) as im2:
                a = im2.convert("RGBA").split()[-1]
            out = out.convert("RGBA")
            out.putalpha(a)
        buf = io.BytesIO()
        out.save(buf, format="PNG", optimize=False)
        tiles[key] = buf.getvalue()
    return tiles


def swatch_sheet(family: Family, *, cell: int = 48) -> bytes:
    """A labelled swatch strip of the family library (TextureBuild catalog)."""
    from PIL import ImageDraw
    n = len(family.colors)
    img = Image.new("RGB", (cell * n, cell + 16), (28, 28, 28))
    d = ImageDraw.Draw(img)
    for i, c in enumerate(family.colors):
        d.rectangle([i * cell, 0, (i + 1) * cell - 1, cell - 1], fill=_hex_255(c))
        d.text((i * cell + 3, cell + 3), c[1:], fill=(210, 210, 210))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def _hex_255(s: str) -> tuple[int, int, int]:
    r, g, b = _hex(s)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))
