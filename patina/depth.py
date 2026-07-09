"""Depth & cohesion cues (v0.12): colour-theory shading, not flat multiply.

Patina's nuance AO/grime darken *value* only — a flat multiply, which is
exactly the "mix black into the shadow, smudge the in-between, get a grey dull
result" mistake Arne Jansson's PSG tutorial calls out. Painters get depth from
colour moves, not brightness moves:

* **Saturated shadow gradients** (Jansson, "saturated gradients"; Artists &
  Illustrators colour-theory) — the transition into shadow/cavity should *gain
  saturation* and shift a touch warm or cool, not just go darker. A blended
  midtone looks lifeless; a saturated one reads as form.
* **Atmospheric perspective** (every depth source) — surfaces that recede
  (here: height, and distance from the building centroid) drift toward a
  desaturated, cool, slightly lighter tint, the way distance fades toward
  sky-grey. This separates planes so a facade reads as depth rather than a flat
  wall.
* **Texture temperature** (Jansson, "Texture" — "alternating a warm and dark
  colour makes the average appear more dimensional and rich") — per-cell
  variation should nudge *hue temperature*, not only brightness, so a tiled
  surface reads richer than monotone. (Applied in :mod:`patina.patterns`.)

All of this is baked into vertex colour (and, for texture temperature, into the
tile), because a PS1-era look has no real-time GI to supply it — the depth must
live in the albedo/vertex data. That is a deliberate, stylistic departure from
a strict PBR *albedo* map (pure unlit base colour): here the "diffuse" carries
soft, view-independent depth cues on purpose.

Everything is deterministic and opt-in. With depth off (the default until a
theme/skin/flag enables it) vertex colour is byte-identical to v0.11.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DepthOptions:
    """Strengths for the depth pass. All 0 => no-op (byte-identical)."""

    shadow_sat: float = 0.0       # saturation gain toward cavity/shadow (0-1)
    shadow_warm: float = 0.0      # hue shift toward warm (+) / cool (-) in shadow
    atmos: float = 0.0            # atmospheric recession strength (0-1)
    atmos_height: float = 0.0     # recession from height (share of atmos)
    atmos_radial: float = 0.0     # recession from centroid distance (share)

    def active(self) -> bool:
        return (self.shadow_sat or self.shadow_warm or self.atmos)

    @classmethod
    def preset(cls, name: str) -> "DepthOptions":
        return dict(_PRESETS)[name]


# The recession target: a desaturated cool sky-grey (atmospheric perspective
# pulls receding surfaces toward this). Kept muted so it reads as air, not fog.
_ATMOS_TARGET = np.array([0.62, 0.66, 0.72], np.float32)   # slightly cool grey
_WARM = np.array([1.0, 0.86, 0.66], np.float32)            # shadow warm bias
_COOL = np.array([0.72, 0.82, 1.0], np.float32)            # shadow cool bias

_PRESETS: dict[str, DepthOptions] = {
    # a restrained late-90s interior/exterior look: warm deepening shadows,
    # gentle recession by height (upper walls fade toward the ceiling haze).
    "delco": DepthOptions(shadow_sat=0.35, shadow_warm=0.12, atmos=0.22,
                          atmos_height=0.7, atmos_radial=0.3),
    # stronger separation for larger exteriors.
    "exterior": DepthOptions(shadow_sat=0.3, shadow_warm=-0.05, atmos=0.35,
                             atmos_height=0.5, atmos_radial=0.5),
    "off": DepthOptions(),
}


def preset_names() -> list[str]:
    return sorted(_PRESETS)


def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """Vectorised RGB->HSV for an (N,3) array in 0..1."""
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    mx = rgb.max(1)
    mn = rgb.min(1)
    diff = mx - mn
    h = np.zeros_like(mx)
    mask = diff > 1e-9
    # hue per dominant channel
    rmax = (mx == r) & mask
    gmax = (mx == g) & mask & ~rmax
    bmax = (mx == b) & mask & ~rmax & ~gmax
    h[rmax] = ((g[rmax] - b[rmax]) / diff[rmax]) % 6
    h[gmax] = ((b[gmax] - r[gmax]) / diff[gmax]) + 2
    h[bmax] = ((r[bmax] - g[bmax]) / diff[bmax]) + 4
    h = h / 6.0
    s = np.where(mx > 1e-9, diff / np.maximum(mx, 1e-9), 0.0)
    return np.stack([h, s, mx], axis=1)


def _hsv_to_rgb(hsv: np.ndarray) -> np.ndarray:
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    out = np.zeros((len(h), 3), np.float32)
    conds = [i == k for k in range(6)]
    reds = [v, q, p, p, t, v]
    greens = [t, v, v, q, p, p]
    blues = [p, p, t, v, v, q]
    for k in range(6):
        out[conds[k], 0] = reds[k][conds[k]]
        out[conds[k], 1] = greens[k][conds[k]]
        out[conds[k], 2] = blues[k][conds[k]]
    return out


def apply_shadow_gradient(rgb: np.ndarray, shadow: np.ndarray,
                          opts: DepthOptions) -> np.ndarray:
    """Saturated, temperature-shifted shadow instead of a flat value multiply.

    ``shadow`` is a per-vertex 0..1 "how deep in shadow/cavity" weight (1 =
    darkest). Toward shadow we *raise saturation* and bias hue warm/cool, so the
    transition reads as form rather than a grey blend. Value darkening is left
    to the caller's existing AO/grime multiply — this only adds the colour.
    """
    if not (opts.shadow_sat or opts.shadow_warm):
        return rgb
    hsv = _rgb_to_hsv(rgb)
    w = np.clip(shadow, 0.0, 1.0)
    # saturation gain toward shadow (Jansson: gradients are saturated)
    hsv[:, 1] = np.clip(hsv[:, 1] + opts.shadow_sat * w, 0.0, 1.0)
    out = _hsv_to_rgb(hsv)
    # temperature bias toward shadow: lerp a small amount to warm/cool tint
    if opts.shadow_warm:
        bias = _WARM if opts.shadow_warm > 0 else _COOL
        amt = (abs(opts.shadow_warm) * w)[:, None]
        out = out * (1.0 - amt) + (out * bias) * amt
    return np.clip(out, 0.0, 1.0)


def apply_atmospheric(rgb: np.ndarray, recede: np.ndarray,
                      opts: DepthOptions) -> np.ndarray:
    """Pull receding vertices toward the cool desaturated atmosphere target.

    ``recede`` is a per-vertex 0..1 recession weight (1 = farthest/highest).
    A partial lerp toward :data:`_ATMOS_TARGET` desaturates, cools and slightly
    lightens receding surfaces — plane separation via atmospheric perspective.
    """
    if not opts.atmos:
        return rgb
    amt = (opts.atmos * np.clip(recede, 0.0, 1.0))[:, None]
    return np.clip(rgb * (1.0 - amt) + _ATMOS_TARGET * amt, 0.0, 1.0)


def recession_weight(positions: np.ndarray, up_axis: int,
                     z_range: tuple[float, float], centroid: np.ndarray,
                     opts: DepthOptions) -> np.ndarray:
    """Per-vertex recession weight from height and radial distance.

    Height: higher surfaces recede (toward ceiling/sky haze). Radial: surfaces
    farther from the building centroid (in the horizontal plane) recede. The two
    are mixed by ``atmos_height`` / ``atmos_radial`` (normalised).
    """
    zmin, zmax = z_range
    span = max(zmax - zmin, 1e-6)
    height = np.clip((positions[:, up_axis] - zmin) / span, 0.0, 1.0)

    horiz = [a for a in range(3) if a != up_axis]
    d = np.sqrt((positions[:, horiz[0]] - centroid[horiz[0]]) ** 2
                + (positions[:, horiz[1]] - centroid[horiz[1]]) ** 2)
    dmax = float(d.max()) if d.size else 1.0
    radial = d / max(dmax, 1e-6)

    wh, wr = opts.atmos_height, opts.atmos_radial
    total = wh + wr
    if total <= 1e-9:
        return height
    return (wh * height + wr * radial) / total
