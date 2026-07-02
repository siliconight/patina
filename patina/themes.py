"""Theme presets — the heart of the texture/colour bashing direction.

A theme bundles everything that makes one gameplay layout read as a specific
*place* without touching playability: a named palette, per-role vertex tints,
per-role albedo variants for the procedural tiles, role aliasing, and decal
pools. One locked greybox + N themes = N looks, all seeded and rebuildable.

Design rules carried over from the bashing-tool brief:

* Themes change **materials, colours and decals only**. Collision, nav
  geometry and gameplay anchors are untouchable by construction (themes have
  no vocabulary to express them).
* The ``default`` theme keeps Patina v0.1.x tints and tiles: no colour
  constants change, and the new ``exterior_wall`` / ``roof`` roles alias back
  onto ``wall`` / ``ceiling`` so the generated texture set is byte-identical.
  (One deliberate visual delta remains: v0.2's classifier now reads up-facing
  faces at the shell's top as ``roof`` — v0.1.x mis-tinted them as ``floor``.)
  Themed looks are strictly opt-in.
* A theme is plain JSON. Builtins ship in-package; ``--theme path/to.json``
  loads a user file with the same shape, so project-specific presets live in
  the project, not in Patina.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from .mesh import SurfaceRole

# Roles a theme may address. Kept in one place so validation errors are exact.
_VALID_ROLES = {r.value for r in SurfaceRole}

# Decal orientation modes: free rotation vs world-vertical (streaks, drips).
_VALID_ROT = {"random", "vertical"}


def _hex_rgb(s: str) -> tuple[float, float, float]:
    """``#rrggbb`` -> linear-ish 0..1 floats. Raises ValueError on junk."""
    t = s.strip().lstrip("#")
    if len(t) != 6:
        raise ValueError(f"bad hex colour {s!r} (want #rrggbb)")
    try:
        return tuple(int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as e:
        raise ValueError(f"bad hex colour {s!r}") from e


@dataclass(frozen=True)
class DecalSpec:
    """One decal pool entry: what to stamp, where, how often, how big."""

    type: str                                  # texture generator key (decals.py)
    roles: tuple[str, ...]                     # surface roles it may land on
    per_100m2: float                           # target density
    size: tuple[float, float]                  # min/max width, world metres
    aspect: tuple[float, float] = (0.8, 1.25)  # height = width * aspect
    rot: str = "random"                        # "random" | "vertical"
    max_count: int = 256                       # hard budget clamp per spec


@dataclass(frozen=True)
class Theme:
    name: str
    palette: dict[str, str] = field(default_factory=dict)   # named hexes (doc/manifest)
    tint: dict[str, str] = field(default_factory=dict)      # role -> vertex-tint hex
    albedo: dict[str, list[str]] = field(default_factory=dict)  # role -> tile hex variants
    alias: dict[str, str] = field(default_factory=dict)     # role -> material key
    decals: tuple[DecalSpec, ...] = ()
    source: str = "builtin"

    def material_key(self, role: str) -> str:
        """The texture-tile key a role resolves to (identity unless aliased)."""
        return self.alias.get(role, role)

    def tint_rgb(self, role: str) -> tuple[float, float, float] | None:
        h = self.tint.get(self.material_key(role)) or self.tint.get(role)
        return _hex_rgb(h) if h else None

    def albedo_variants(self, key: str) -> list[tuple[float, float, float]]:
        return [_hex_rgb(h) for h in self.albedo.get(key, [])]


# ---------------------------------------------------------------------------
# Builtin themes
# ---------------------------------------------------------------------------

# v0.1.x constants, exactly. Tints fall back to nuance._BASE_TINT; albedo to
# palette._ALBEDO; the two new classification roles alias onto their old
# umbrella roles so the generated tile set is byte-identical to v0.1.x.
_DEFAULT = {
    "name": "default",
    "palette": {},
    "alias": {"exterior_wall": "wall", "roof": "ceiling"},
    "tint": {},      # empty -> nuance falls back to its built-in constants
    "albedo": {},    # empty -> palette falls back to its built-in constants
    "decals": [],
}

# The brief's flagship preset: Delco 1997 gas station. Faded sun-bleached
# stucco, oxblood trim, teal accents, three decades of grime.
_DELCO_GAS = {
    "name": "delco_1997_gas_station",
    "palette": {
        "primary": "#d8c78f", "secondary": "#9b2f24",
        "accent": "#2e6f7e", "grime": "#2a241f",
    },
    "alias": {},
    "tint": {
        "floor": "#9e968a", "wall": "#c2bcae", "exterior_wall": "#cfc3a0",
        "ceiling": "#a8a89f", "roof": "#7d7a74", "trim": "#b08b86",
        "unknown": "#b8b8b8",
    },
    "albedo": {
        "floor": ["#6b6257", "#7a6f5e", "#5d564d"],         # worn lino/concrete
        "wall": ["#cfc9b8", "#c4b89a"],                     # yellowed interior
        "exterior_wall": ["#d8c78f", "#c9b478", "#b8a878"], # faded stucco
        "ceiling": ["#8d8d86"],
        "roof": ["#4a4642", "#3f3c39"],                     # tar roof
        "trim": ["#9b2f24", "#2e6f7e"],                     # oxblood / teal
        "unknown": ["#999990"],
    },
    "decals": [
        {"type": "water_stain", "roles": ["wall", "ceiling"],
         "per_100m2": 6.0, "size": [0.5, 1.2]},
        {"type": "paint_chip", "roles": ["wall", "exterior_wall"],
         "per_100m2": 5.0, "size": [0.2, 0.6]},
        {"type": "rust_streak", "roles": ["exterior_wall"],
         "per_100m2": 5.0, "size": [0.25, 0.6],
         "aspect": [2.2, 3.5], "rot": "vertical"},
        {"type": "oil_stain", "roles": ["floor"],
         "per_100m2": 4.0, "size": [0.6, 1.4]},
        {"type": "scuff_marks", "roles": ["floor"],
         "per_100m2": 8.0, "size": [0.3, 0.8]},
        {"type": "gum_spot", "roles": ["floor"],
         "per_100m2": 10.0, "size": [0.08, 0.18]},
    ],
}

_BUILTINS: dict[str, dict] = {
    "default": _DEFAULT,
    "delco_1997_gas_station": _DELCO_GAS,
}


def builtin_names() -> list[str]:
    return sorted(_BUILTINS)


def _parse(raw: dict, source: str) -> Theme:
    name = raw.get("name")
    if not name or not isinstance(name, str):
        raise ValueError(f"theme {source}: missing 'name'")

    for block in ("tint",):
        for role, h in (raw.get(block) or {}).items():
            if role not in _VALID_ROLES:
                raise ValueError(f"theme {name}: unknown role {role!r} in {block}")
            _hex_rgb(h)
    for role, variants in (raw.get("albedo") or {}).items():
        if role not in _VALID_ROLES:
            raise ValueError(f"theme {name}: unknown role {role!r} in albedo")
        if not isinstance(variants, list) or not variants:
            raise ValueError(f"theme {name}: albedo[{role!r}] must be a non-empty list")
        for h in variants:
            _hex_rgb(h)
    for src, dst in (raw.get("alias") or {}).items():
        if src not in _VALID_ROLES or dst not in _VALID_ROLES:
            raise ValueError(f"theme {name}: bad alias {src!r} -> {dst!r}")
    for h in (raw.get("palette") or {}).values():
        _hex_rgb(h)

    specs: list[DecalSpec] = []
    for i, d in enumerate(raw.get("decals") or []):
        roles = tuple(d.get("roles") or ())
        if not roles or any(r not in _VALID_ROLES for r in roles):
            raise ValueError(f"theme {name}: decal[{i}] bad roles {roles!r}")
        size = d.get("size") or []
        if len(size) != 2 or not (0 < size[0] <= size[1]):
            raise ValueError(f"theme {name}: decal[{i}] bad size {size!r}")
        rot = d.get("rot", "random")
        if rot not in _VALID_ROT:
            raise ValueError(f"theme {name}: decal[{i}] bad rot {rot!r}")
        aspect = d.get("aspect", [0.8, 1.25])
        if len(aspect) != 2 or not (0 < aspect[0] <= aspect[1]):
            raise ValueError(f"theme {name}: decal[{i}] bad aspect {aspect!r}")
        specs.append(DecalSpec(
            type=str(d.get("type", "")) or "grime",
            roles=roles,
            per_100m2=float(d.get("per_100m2", 1.0)),
            size=(float(size[0]), float(size[1])),
            aspect=(float(aspect[0]), float(aspect[1])),
            rot=rot,
            max_count=int(d.get("max_count", 256)),
        ))

    return Theme(
        name=name,
        palette=dict(raw.get("palette") or {}),
        tint=dict(raw.get("tint") or {}),
        albedo={k: list(v) for k, v in (raw.get("albedo") or {}).items()},
        alias=dict(raw.get("alias") or {}),
        decals=tuple(specs),
        source=source,
    )


def load(name_or_path: str) -> Theme:
    """Builtin theme by name, or a user theme from a JSON file path."""
    if name_or_path in _BUILTINS:
        return _parse(_BUILTINS[name_or_path], "builtin")
    if os.path.exists(name_or_path):
        with open(name_or_path, "r", encoding="utf-8") as fh:
            return _parse(json.load(fh), name_or_path)
    raise ValueError(
        f"unknown theme {name_or_path!r}; builtins: {', '.join(builtin_names())} "
        f"(or pass a path to a theme .json)")
