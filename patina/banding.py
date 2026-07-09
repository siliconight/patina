"""Vertical banding (v0.7): material variation by world height.

Real buildings rarely use one material top-to-bottom — a base course of
brick, painted concrete in the middle, metal flashing at the cap. This is the
"material variation" / "color blocking" art-pass move (and the cheapest big
win on a greybox): it reads as a building instead of a box, and it costs *no
geometry* — bands are chosen per vertex by world height and baked into vertex
colour, riding the existing nuance pass. In procedural mode the band tint
multiplies the tiled albedo, so a shared cinderblock pattern still reads as
brick-at-the-base / concrete-in-the-middle.

A band spec is per vertical role::

    "bands": {
        "wall": [
            {"to": 0.30, "tint": "#6e2a24"},   # base course (bottom 30%)
            {"to": 0.92, "tint": "#726d61"},   # body
            {"to": 1.00, "tint": "#a98a52"}    # cap / flashing
        ]
    }

``to`` is a fraction of the shell's vertical extent (0 = floor, 1 = ceiling),
ascending; the last band is forced to 1.0. Only *vertical* roles band
(``wall`` / ``exterior_wall`` / ``trim``) — floors, ceilings and roofs are not
vertical spans. The fraction uses the **global** visual-AABB Z range so bands
land at consistent world heights across every wall (correct for the
single-storey blockouts Deli Counter emits; multi-storey shells would want
per-wall normalisation, noted as future work).

Colours are ordinary palette hexes, so a bound family locks them too. Skins
auto-derive bands from their 60/30/10 (base = a shadow, body = a base, cap =
the accent). No band spec -> the pass is a no-op and vertex colour is
byte-identical to v0.6.
"""

from __future__ import annotations

import numpy as np

from .mesh import SurfaceRole
from .themes import _hex_rgb

#: Roles that are vertical spans and may band. Others are ignored if declared.
BANDED_ROLES = (SurfaceRole.WALL, SurfaceRole.EXTERIOR_WALL, SurfaceRole.TRIM)
_BANDED_VALUES = {r.value for r in BANDED_ROLES}


def validate_spec(raw: dict, where: str) -> None:
    """Raise ValueError on a malformed ``bands`` block (theme-load time)."""
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: bands must be an object of role -> band list")
    for role, bands in raw.items():
        if role not in _BANDED_VALUES:
            raise ValueError(
                f"{where}: role {role!r} cannot band (vertical roles only: "
                f"{sorted(_BANDED_VALUES)})")
        if not isinstance(bands, list) or not bands:
            raise ValueError(f"{where}: bands[{role!r}] must be a non-empty list")
        last = 0.0
        for i, b in enumerate(bands):
            if not isinstance(b, dict) or "to" not in b or "tint" not in b:
                raise ValueError(f"{where}: bands[{role!r}][{i}] needs 'to' and 'tint'")
            to = b["to"]
            if not isinstance(to, (int, float)) or not (0.0 < to <= 1.0):
                raise ValueError(f"{where}: bands[{role!r}][{i}].to must be in (0, 1]")
            if to < last:
                raise ValueError(f"{where}: bands[{role!r}] 'to' values must ascend")
            last = to
            try:
                _hex_rgb(b["tint"])
            except ValueError as e:
                raise ValueError(f"{where}: bands[{role!r}][{i}] bad tint") from e


def parse(raw: dict | None) -> dict[SurfaceRole, list[tuple[float, np.ndarray]]]:
    """Normalise a raw bands block to ``{role: [(to, rgb), ...]}``.

    Sorted ascending, last boundary clamped to 1.0 so the top band always
    reaches the ceiling.
    """
    out: dict[SurfaceRole, list[tuple[float, np.ndarray]]] = {}
    for role, bands in (raw or {}).items():
        if role not in _BANDED_VALUES:
            continue
        pairs = sorted(((float(b["to"]), np.array(_hex_rgb(b["tint"]), np.float32))
                        for b in bands), key=lambda p: p[0])
        if pairs:
            pairs[-1] = (1.0, pairs[-1][1])
        out[SurfaceRole(role)] = pairs
    return out


def lock(bands: dict[SurfaceRole, list[tuple[float, np.ndarray]]],
         family) -> dict[SurfaceRole, list[tuple[float, np.ndarray]]]:
    """Quantise every band colour to a family (so bands share the library)."""
    return {role: [(to, np.array(family_lock_tint(rgb, family), np.float32))
                   for to, rgb in pairs]
            for role, pairs in bands.items()}


def family_lock_tint(rgb, family):
    from . import families
    return families.lock_tint((float(rgb[0]), float(rgb[1]), float(rgb[2])), family)


def band_rgb(pairs: list[tuple[float, np.ndarray]], frac: float) -> np.ndarray:
    """The band colour for a height fraction (first band whose ``to >= frac``)."""
    for to, rgb in pairs:
        if frac <= to:
            return rgb
    return pairs[-1][1]


def vertex_band_tints(positions: np.ndarray, roles: np.ndarray,
                      bands: dict[SurfaceRole, list[tuple[float, np.ndarray]]],
                      z_range: tuple[float, float],
                      base_tint: np.ndarray, up_axis: int = 2) -> np.ndarray:
    """Return a (V,3) tint array: band colour for banded-role vertices, else
    the supplied per-vertex ``base_tint``. Height fraction is global, taken
    along ``up_axis`` (2=Z for legacy shells, 1=Y for DC glTF exports).
    """
    zmin, zmax = z_range
    span = max(zmax - zmin, 1e-6)
    out = base_tint.copy()
    for i, role in enumerate(roles):
        pairs = bands.get(role)
        if pairs:
            frac = float(np.clip((positions[i, up_axis] - zmin) / span, 0.0, 1.0))
            out[i] = band_rgb(pairs, frac)
    return out
