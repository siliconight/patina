"""Single source of truth for the Patina version.

The version string is baked into the glTF ``asset.generator`` field and the
``.patina.json`` manifest so that output is traceable to the exact tool
revision that produced it. It is *fixed per release* (never a timestamp), which
is what keeps output byte-identical across runs on the same code.
"""

__version__ = "0.16.0"

# Manifest schema version. Bump independently of the tool version when the
# .patina.json shape changes in a backward-incompatible way.
MANIFEST_SCHEMA_VERSION = "0.2.0"

# Default determinism seed. Matches the Deli Counter convention (1999) so the
# two tools tell the same story about reproducibility.
DEFAULT_SEED = 1999
