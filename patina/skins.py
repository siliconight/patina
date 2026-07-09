"""Procedural skins (v0.6): generate a structured skin from hex + style.

Where v0.5 *extracts* a family from a photo, this *generates* one from a few
hex seed colours plus a style — the counterpart move. It follows the same
colour theory as GabagoolStudios' Color Swatch add-on
(github.com/siliconight/color_swatch): a **60/30/10** structure (a calm
*dominant*, a mid *secondary*, a punchy *accent*), each expanded into a
**shadow / base / light** family. Color Swatch authors these palettes by hand
from liked colours; this module derives the same shape headlessly so a level
can be skinned straight from a palette.

Inputs:

* **seeds** — 1-3 hex colours ("like hexadecimal"). Seed 0 sets the dominant
  hue; seeds 1 and 2, if given, pin the secondary and accent directly.
  Missing slots are filled by the style's **harmony** (monochrome / analogous
  / complementary / triad / split-complementary — hue rotations in HSV).
* **style** — a mood: saturation/value discipline and shadow/light contrast
  (e.g. ``faded``, ``grimy``, ``neon``, ``clean``, ``sunbleached``,
  ``nicotine``). Each style names a default harmony and a default seed, so
  ``--skin grimy`` works with no colours at all.

Output is a :class:`Skin`: per-role albedo variants and vertex tints (mapped
by the 60/30/10 area logic — big surfaces get dominant/secondary, trim gets
the accent), plus a :class:`~patina.families.Family` (the flat shadow/base/
light library) for the palette-lock pass. Applying a skin is: fold its
albedo/tint into the theme, then lock to its family — reusing the v0.4/v0.5
plumbing, no new tile or lock logic.

Fully deterministic: colour math only, no RNG.
"""

from __future__ import annotations

import colorsys
import json
import os
from dataclasses import dataclass, field

from . import families
from .mesh import SurfaceRole

# Hue offsets (degrees) for [dominant, secondary, accent] per harmony.
HARMONIES: dict[str, tuple[float, float, float]] = {
    "monochrome": (0.0, 0.0, 0.0),
    "analogous": (0.0, 30.0, -30.0),
    "complementary": (0.0, 30.0, 180.0),
    "triad": (0.0, 120.0, 240.0),
    "split_complementary": (0.0, 150.0, 210.0),
}

# style -> discipline. sat/val scale the whole palette; shadow_v/light_v are
# the value multipliers for the shadow/light ends; accent_sat punches the 10%;
# harmony + seed are the defaults when the caller doesn't pin them.
STYLES: dict[str, dict] = {
    "faded":       {"sat": 0.55, "val": 0.05, "shadow_v": 0.72, "light_v": 1.12,
                    "accent_sat": 0.9,  "harmony": "analogous", "seed": "#8f8877"},
    "grimy":       {"sat": 0.60, "val": -0.08, "shadow_v": 0.58, "light_v": 1.10,
                    "accent_sat": 1.0,  "harmony": "monochrome", "seed": "#55524a"},
    "neon":        {"sat": 1.15, "val": 0.0,  "shadow_v": 0.5,  "light_v": 1.3,
                    "accent_sat": 1.4,  "harmony": "complementary", "seed": "#245055"},
    "clean":       {"sat": 0.9,  "val": 0.05, "shadow_v": 0.7,  "light_v": 1.2,
                    "accent_sat": 1.1,  "harmony": "analogous", "seed": "#726d61"},
    "sunbleached": {"sat": 0.45, "val": 0.12, "shadow_v": 0.78, "light_v": 1.15,
                    "accent_sat": 0.85, "harmony": "analogous", "seed": "#c9c3ad"},
    "nicotine":    {"sat": 0.7,  "val": -0.03, "shadow_v": 0.62, "light_v": 1.1,
                    "accent_sat": 1.05, "harmony": "split_complementary",
                    "seed": "#a98a52"},
}

# Which 60/30/10 slot + value each surface role draws from. The 10% accent
# lands on trim (textbook), big areas take dominant/secondary.
_ROLE_SLOT: dict[str, tuple[str, str, str]] = {
    # role: (slot, primary variant, secondary variant for albedo variety)
    "floor":         ("dominant", "shadow", "base"),
    "wall":          ("dominant", "base", "light"),
    "ceiling":       ("secondary", "light", "base"),
    "exterior_wall": ("secondary", "base", "shadow"),
    "roof":          ("secondary", "shadow", "base"),
    "trim":          ("accent", "base", "light"),
}


def style_names() -> list[str]:
    return sorted(STYLES)


# --------------------------------------------------------------------------- #
# Colour math
# --------------------------------------------------------------------------- #

def _hex_to_hsv(h: str) -> tuple[float, float, float]:
    t = h.strip().lstrip("#")
    if len(t) != 6:
        raise ValueError(f"bad hex {h!r} (want '#rrggbb')")
    r, g, b = (int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)


def _hsv_to_hex(h: float, s: float, v: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, _clamp(s), _clamp(v))
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _clamp(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _family_triad(hue: float, sat: float, val: float, st: dict) -> dict[str, str]:
    """shadow / base / light for one slot, at a given hue."""
    return {
        "shadow": _hsv_to_hex(hue, sat * 1.05, val * st["shadow_v"]),
        "base":   _hsv_to_hex(hue, sat, val),
        "light":  _hsv_to_hex(hue, sat * 0.9, val * st["light_v"]),
    }


# --------------------------------------------------------------------------- #
# Skin
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Skin:
    name: str
    slots: dict[str, dict[str, str]]        # dominant/secondary/accent -> {shadow,base,light}
    albedo: dict[str, list[str]] = field(default_factory=dict)  # role -> hex variants
    tint: dict[str, str] = field(default_factory=dict)          # role -> hex
    style: str = ""
    harmony: str = ""

    def family(self) -> families.Family:
        """Flat shadow/base/light library across all three slots (the lock
        palette) — luma-sorted, deduped by families._make."""
        colors = [c for slot in ("dominant", "secondary", "accent")
                  for c in self.slots[slot].values()]
        return families._make(f"{self.name}_family", colors, None, "skin")

    def bands(self) -> dict[str, list[dict]]:
        """Vertical material bands auto-derived from the 60/30/10: a darker
        base course, the body, and the accent as a cap/flashing line."""
        d, s, a = (self.slots["dominant"], self.slots["secondary"],
                   self.slots["accent"])
        return {
            "wall": [
                {"to": 0.30, "tint": d["shadow"]},
                {"to": 0.92, "tint": d["base"]},
                {"to": 1.00, "tint": a["base"]},
            ],
            "exterior_wall": [
                {"to": 0.30, "tint": s["shadow"]},
                {"to": 0.90, "tint": s["base"]},
                {"to": 1.00, "tint": a["base"]},
            ],
        }


# Per-slot value/saturation steps applied to harmony-FILLED slots so the
# 60/30/10 grades even under monochrome (one hue, varied lightness/sat).
# Pinned seed colours are used as-authored and skip these.
_SLOT_STEP = {
    "dominant":  (1.0, 1.0),
    "secondary": (1.15, 0.88),
    "accent":    (0.95, 1.0),
}


def generate(style: str, seeds: list[str] | None = None, *,
             harmony: str | None = None, name: str | None = None) -> Skin:
    """Build a Skin from a style and up to three hex seeds."""
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r} (want one of {style_names()})")
    st = STYLES[style]
    seeds = list(seeds or [])
    if not seeds:
        seeds = [st["seed"]]
    if len(seeds) > 3:
        raise ValueError("skin takes at most 3 seed colours (dominant, secondary, accent)")
    harm = harmony or st["harmony"]
    if harm not in HARMONIES:
        raise ValueError(f"unknown harmony {harm!r} (want one of {sorted(HARMONIES)})")
    offsets = HARMONIES[harm]

    h0, s0, v0 = _hex_to_hsv(seeds[0])
    sat = _clamp(s0 * st["sat"])
    val = _clamp(v0 + st["val"])

    slots: dict[str, dict[str, str]] = {}
    for i, slot in enumerate(("dominant", "secondary", "accent")):
        if i < len(seeds):
            hi, si, vi = _hex_to_hsv(seeds[i])      # pinned by the user's hex
            hue = hi
            s_i, v_i = _clamp(si * st["sat"]), _clamp(vi + st["val"])
        else:
            hue = h0 + offsets[i] / 360.0           # filled by harmony
            vstep, sstep = _SLOT_STEP[slot]
            s_i, v_i = _clamp(sat * sstep), _clamp(val * vstep)
        if slot == "accent":
            s_i = _clamp(s_i * st["accent_sat"])
        slots[slot] = _family_triad(hue, s_i, v_i, st)

    albedo, tint = _role_maps(slots)
    return Skin(name=name or f"{style}_skin", slots=slots, albedo=albedo,
                tint=tint, style=style, harmony=harm)


def _role_maps(slots: dict[str, dict[str, str]]) \
        -> tuple[dict[str, list[str]], dict[str, str]]:
    albedo: dict[str, list[str]] = {}
    tint: dict[str, str] = {}
    for role, (slot, v1, v2) in _ROLE_SLOT.items():
        fam = slots[slot]
        albedo[role] = [fam[v1], fam[v2]]
        tint[role] = fam[v1]
    return albedo, tint


# --------------------------------------------------------------------------- #
# Color Swatch interop
# --------------------------------------------------------------------------- #

def from_swatch_palette(data: dict, *, style: str = "clean",
                        name: str | None = None) -> Skin:
    """Import a Color-Swatch-style saved 60/30/10 palette.

    Accepts ``{dominant/secondary/accent: {shadow, base, light}}`` (the shape
    Color Swatch's *Generate 60/30/10* produces). The style only sets the
    role→slot mapping discipline here; the colours are taken as authored.
    """
    slots = {}
    for slot in ("dominant", "secondary", "accent"):
        entry = data.get(slot)
        if not isinstance(entry, dict) or not {"shadow", "base", "light"} <= set(entry):
            raise ValueError(f"palette missing {slot!r} shadow/base/light")
        for k in ("shadow", "base", "light"):
            _hex_to_hsv(entry[k])                   # validate
        slots[slot] = {k: entry[k] for k in ("shadow", "base", "light")}
    albedo, tint = _role_maps(slots)
    return Skin(name=name or "swatch_palette", slots=slots, albedo=albedo,
                tint=tint, style=style, harmony="imported")


def seeds_from_library(path: str, *, limit: int = 3) -> list[str]:
    """Pull up to ``limit`` liked hexes from a color_swatch_library.json.

    Tolerant of the exact key layout: scans for a 'liked' list (any casing)
    of entries that are hex strings or objects carrying a hex/color field.
    Falls back to any top-level hex strings if no explicit liked list.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    liked = None
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k.lower() in ("liked", "likes", "like") and isinstance(v, list):
                liked = v
                break
    hexes = _harvest_hexes(liked if liked is not None else raw)
    if not hexes:
        raise ValueError(f"{path}: no liked hex colours found")
    return hexes[:limit]


def _harvest_hexes(node) -> list[str]:
    out: list[str] = []
    def visit(n):
        if isinstance(n, str) and n.strip().startswith("#") and len(n.strip()) == 7:
            try:
                _hex_to_hsv(n)
                out.append(n.strip())
            except ValueError:
                pass
        elif isinstance(n, dict):
            for key in ("hex", "color", "value"):
                if isinstance(n.get(key), str):
                    visit(n[key])
                    return
            for v in n.values():
                visit(v)
        elif isinstance(n, list):
            for v in n:
                visit(v)
    visit(node)
    return out


def to_swatch_text(skin: Skin) -> str:
    """Export as a Color-Swatch 'Copy as Text' style labelled block."""
    lines = [f"# {skin.name} ({skin.style}/{skin.harmony}) — 60/30/10"]
    for slot in ("dominant", "secondary", "accent"):
        f = skin.slots[slot]
        lines.append(f"{slot.upper():9s} shadow {f['shadow']}  base {f['base']}  "
                     f"light {f['light']}")
    return "\n".join(lines) + "\n"


def to_skin_json(skin: Skin) -> dict:
    """Serialisable record of the generated skin (for <out>.skin.json)."""
    return {
        "name": skin.name, "style": skin.style, "harmony": skin.harmony,
        "slots": skin.slots, "roles": {
            r: {"tint": skin.tint[r], "albedo": skin.albedo[r]} for r in skin.tint},
    }


# --------------------------------------------------------------------------- #
# Application (fold into a theme; the family locks separately)
# --------------------------------------------------------------------------- #

def apply_to_theme(theme, skin: Skin):
    """Effective theme = theme with the skin's per-role albedo + tint folded
    in (patterns/decals/aliases from the theme are kept). Overridden roles
    lose their alias so each surface gets its own skinned tile."""
    import dataclasses
    alias = {k: v for k, v in theme.alias.items() if k not in skin.albedo}
    albedo = {**theme.albedo, **{k: list(v) for k, v in skin.albedo.items()}}
    tint = {**theme.tint, **dict(skin.tint)}
    return dataclasses.replace(theme, alias=alias, albedo=albedo, tint=tint)


def resolve(spec: str, *, seed_from: str | None = None,
            seed: int = 1999) -> Skin:
    """Parse a ``--skin`` value into a Skin.

    ``spec`` = ``STYLE`` or ``STYLE:SEEDS`` where SEEDS is a comma-separated
    hex list, or a path to a color_swatch library / saved-palette json.
    ``seed_from`` (``--skin-from``) is an alternative palette/library file.
    """
    style, _, rest = spec.partition(":")
    src = rest or (seed_from or "")
    if src and os.path.exists(src):
        with open(src, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "dominant" in data:      # saved 60/30/10
            return from_swatch_palette(data, style=style or "clean")
        seeds = seeds_from_library(src)                         # liked colours
        return generate(style or "clean", seeds)
    seeds = [s.strip() for s in src.split(",") if s.strip()] if src else None
    return generate(style or "clean", seeds)
