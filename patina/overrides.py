"""Art-bash overrides (v0.4): per-key substitution over a theme.

The bashing loop needs a middle gear between "regenerate everything"
(``procedural``) and "hand the whole set to a human" (``byo``): run the pass,
walk it, dislike *one* surface, swap *that* surface, run again. An override
substitutes, per material key, any of:

* ``image`` — a texture or photo file. By default it is PS1-ified on import
  (centre-crop to square, resize to the tile size, posterize) so a phone
  photo of a real Delco wall becomes a period-correct tile; ``"process":
  false`` passes the file through untouched (pre-made pixel art).
* ``albedo`` — replacement colour variants for the key (the generated
  pattern/noise is kept, recoloured).
* ``tint`` — replacement vertex-colour base tint for the key.
* ``pattern`` — a replacement pattern spec (same shape as a theme's).

Sources, later wins: theme < ``--overrides file.json`` < repeated
``--override KEY=VALUE`` flags. The JSON file is the *savable* bash session —
it lives in the project repo next to the theme, so a look you arrived at by
bashing is reproducible. CLI ``VALUE`` is either one-or-more hex colours
(``wall=#a1b2c3`` / ``floor=#6b6257,#7a6f5e`` -> albedo) or an image path
(``wall=./ref/brick.jpg``).

Overrides address *material keys*. If a theme aliases a key away (default
aliases ``exterior_wall`` -> ``wall``), overriding that key breaks the alias
for it — "just the exterior walls" means just the exterior walls.

Determinism: colour/pattern overrides are seeded like everything else; image
imports are deterministic functions of the file bytes (same class of
input-dependence as ``byo``).
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field

from . import patterns
from .themes import Theme, _hex_rgb, _VALID_ROLES

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


@dataclass
class Override:
    """Everything one material key may substitute."""

    image: str | None = None          # path to a texture/photo file
    process: bool = True              # PS1-ify the import (crop/resize/posterize)
    albedo: list[str] = field(default_factory=list)   # hex variants
    tint: str | None = None           # hex vertex tint
    pattern: dict | None = None       # pattern spec (patterns.validate_spec)


def _check_key(key: str, where: str) -> None:
    if key not in _VALID_ROLES:
        raise ValueError(f"{where}: unknown material key {key!r} "
                         f"(want one of {sorted(_VALID_ROLES)})")


def _check(ovr: Override, key: str, where: str) -> None:
    _check_key(key, where)
    if ovr.image is not None and not os.path.exists(ovr.image):
        raise ValueError(f"{where}: image not found: {ovr.image}")
    for h in ovr.albedo:
        _hex_rgb(h)
    if ovr.tint is not None:
        _hex_rgb(ovr.tint)
    if ovr.pattern is not None:
        patterns.validate_spec(ovr.pattern, f"{where}: pattern")


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

def parse_cli(pairs: list[str]) -> dict[str, Override]:
    """``KEY=VALUE`` flags. VALUE = hex colour(s) -> albedo, else image path."""
    out: dict[str, Override] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"--override wants KEY=VALUE, got {pair!r}")
        key, value = pair.split("=", 1)
        key, value = key.strip(), value.strip()
        where = f"--override {key}"
        if value.startswith("#"):
            ovr = Override(albedo=[v.strip() for v in value.split(",") if v.strip()])
        else:
            if not value.lower().endswith(_IMAGE_EXTS):
                raise ValueError(f"{where}: value must be #hex colour(s) or an "
                                 f"image path ({'/'.join(_IMAGE_EXTS)}), got {value!r}")
            ovr = Override(image=value)
        _check(ovr, key, where)
        out[key] = ovr
    return out


def load_file(path: str) -> dict[str, Override]:
    """A saved bash session: ``{key: {image|albedo|tint|pattern|process}}``.

    Relative image paths resolve against the JSON file's directory, so the
    overlay is portable alongside the project.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: overrides file must be an object")
    base = os.path.dirname(os.path.abspath(path))
    out: dict[str, Override] = {}
    for key, entry in raw.items():
        where = f"{os.path.basename(path)}: {key}"
        if not isinstance(entry, dict):
            raise ValueError(f"{where}: entry must be an object")
        unknown = set(entry) - {"image", "process", "albedo", "tint", "pattern"}
        if unknown:
            raise ValueError(f"{where}: unknown field(s) {sorted(unknown)}")
        img = entry.get("image")
        if img is not None and not os.path.isabs(img):
            img = os.path.normpath(os.path.join(base, img))
        ovr = Override(
            image=img,
            process=bool(entry.get("process", True)),
            albedo=list(entry.get("albedo") or []),
            tint=entry.get("tint"),
            pattern=entry.get("pattern"),
        )
        _check(ovr, key, where)
        out[key] = ovr
    return out


def merge(*layers: dict[str, Override]) -> dict[str, Override]:
    """Later layers win per key, field-wise (a CLI colour swap on top of a
    file's image swap replaces the albedo, not the image)."""
    out: dict[str, Override] = {}
    for layer in layers:
        for key, ovr in (layer or {}).items():
            if key not in out:
                out[key] = dataclasses.replace(ovr)
                continue
            cur = out[key]
            if ovr.image is not None:
                cur.image, cur.process = ovr.image, ovr.process
            if ovr.albedo:
                cur.albedo = list(ovr.albedo)
            if ovr.tint is not None:
                cur.tint = ovr.tint
            if ovr.pattern is not None:
                cur.pattern = dict(ovr.pattern)
    return out


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #

def apply_to_theme(theme: Theme, ovr: dict[str, Override]) -> Theme:
    """Effective theme = theme with per-key albedo/tint/pattern substituted.

    An overridden key stops being aliased away: it gets its own material
    identity (and therefore its own tile file). Image substitution is not a
    theme concern — it happens on the built tile set (:func:`apply_images`).
    """
    if not ovr:
        return theme
    alias = dict(theme.alias)
    tint = dict(theme.tint)
    albedo = {k: list(v) for k, v in theme.albedo.items()}
    pattern = {k: dict(v) for k, v in theme.pattern.items()}
    for key, o in ovr.items():
        alias.pop(key, None)
        if o.albedo:
            albedo[key] = list(o.albedo)
        if o.tint is not None:
            tint[key] = o.tint
        if o.pattern is not None:
            pattern[key] = dict(o.pattern)
    return dataclasses.replace(theme, alias=alias, tint=tint,
                               albedo=albedo, pattern=pattern)


def apply_images(tiles: dict[str, bytes], ovr: dict[str, Override],
                 opts) -> list[str]:
    """Substitute imported images into a built tile set, in place.

    ``opts`` is the :class:`patina.palette.PaletteOptions` in effect (size and
    posterize drive the PS1-ification). Returns the keys that were replaced.
    Keys with an image override that produced no tile (role unused in the
    scene) are ignored — nothing to skin.
    """
    from . import palette   # local import: palette imports nothing from here
    replaced = []
    for key, o in ovr.items():
        if o.image is None or key not in tiles:
            continue
        tiles[key] = palette.import_tile(o.image, opts, process=o.process)
        replaced.append(key)
    return sorted(replaced)


def describe(ovr: dict[str, Override]) -> dict[str, str]:
    """Human-readable per-key summary for the CLI report."""
    out = {}
    for key, o in sorted(ovr.items()):
        bits = []
        if o.image:
            bits.append(f"image={os.path.basename(o.image)}"
                        + ("" if o.process else " (raw)"))
        if o.albedo:
            bits.append("albedo=" + ",".join(o.albedo))
        if o.tint:
            bits.append(f"tint={o.tint}")
        if o.pattern:
            bits.append(f"pattern={o.pattern.get('type')}")
        out[key] = " ".join(bits)
    return out
