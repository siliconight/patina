#!/usr/bin/env python3
"""Offline pipeline smoke test — prove the art-pass flow holds, end to end.

Runs the stages that don't need Blender/Godot and *asserts* each produced valid,
correctly-shaped output. This is the guard rail: when a DC spec, a Zoo species,
or a coordinate convention drifts, this fails loudly at the exact stage instead
of surfacing three steps later as a black roof in Godot.

What it checks, per stage:
  1. DC manifest    — a real <name>.slots.json parses, has slots + up-axis
  2. Patina         — a full art-pass run on the DC glb produces every artifact
  3. Patina output  — glb loads, collision tri-count unchanged (never touched),
                      vertex colour in range (no crush), depth/slot/anchors sane
  4. contracts      — dressing.json + instances.json match their schemas and
                      the Zoo planner accepts the dressing manifest
  5. headroom       — the composite preview reports OK (not TOO DARK)

Usage:
    python smoke_offline.py <deli_counter_build_dir> [--zoo <zoo_repo>]

Exit 0 = every stage green. Non-zero = the failing stage is named.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

# ---- tiny assert harness --------------------------------------------------- #
_PASS, _FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
_fails: list[str] = []


def check(stage: str, cond: bool, detail: str = "") -> None:
    tag = _PASS if cond else _FAIL
    print(f"  [{tag}] {stage}" + (f" — {detail}" if detail else ""))
    if not cond:
        _fails.append(stage)


def stage(name: str) -> None:
    print(f"\n=== {name} ===")


# ---- the smoke test -------------------------------------------------------- #

def run(build_dir: str, zoo_repo: str | None) -> int:
    building = "gs_corner_station"
    glb = os.path.join(build_dir, f"{building}.glb")
    slots_json = os.path.join(build_dir, f"{building}.slots.json")

    stage("1. Deli Counter output")
    check("glb exists", os.path.isfile(glb), glb)
    check("slots.json exists", os.path.isfile(slots_json))
    if not (os.path.isfile(glb) and os.path.isfile(slots_json)):
        print("\nDC output missing — cannot continue.")
        return 1
    man = json.load(open(slots_json))
    check("slots.json has slots", len(man.get("slots", [])) > 0,
          f"{len(man.get('slots', []))} slots")
    check("slot_manifest_version present", "slot_manifest_version" in man,
          man.get("slot_manifest_version"))
    check("Blender Z-up space declared", "Blender" in man.get("space", ""))

    stage("2. Patina art-pass (full stack)")
    out = os.path.join(tempfile.mkdtemp(), "gs.patina.glb")
    cmd = [sys.executable, "-m", "patina.cli", glb, "--mode", "procedural",
           "--depth", "lux", "--slot-variation", "--anchors", "--dressing",
           "--preview", "--out", out]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    check("patina exited 0", proc.returncode == 0,
          proc.stderr.strip().splitlines()[-1] if proc.returncode else "")
    stem = out[:-4]
    artifacts = {
        "styled glb": out,
        "manifest": stem + ".json",
        "preview": stem + ".preview.png",
        "dressing": stem + ".dressing.json",
        "instances": stem + ".instances.json",
        "anchors": stem + ".anchors.json",
        "trim sheet": stem + ".trim.png",
    }
    for label, path in artifacts.items():
        check(f"produced {label}", os.path.isfile(path))

    stage("3. Patina output integrity")
    try:
        sys.path.insert(0, _patina_repo())
        from patina import gltf_io
        styled = gltf_io.load_glb(out)
        src = gltf_io.load_glb(glb)

        def coll_tris(s):
            return sum(p.triangle_count() for m in s.meshes
                       for p in m.primitives if m.kind.name == "COLLISION")
        check("collision tris unchanged", coll_tris(styled) == coll_tris(src),
              f"{coll_tris(src)} -> {coll_tris(styled)}")

        import numpy as np
        cols = np.vstack([p.color[:, :3] for m in styled.visual_meshes()
                          for p in m.primitives if p.color is not None])
        check("vertex colour in [0,1]", float(cols.min()) >= 0
              and float(cols.max()) <= 1.0)
        check("vertex colour not crushed", float(cols.mean()) > 0.15,
              f"mean {cols.mean():.3f}")
    except Exception as e:                       # noqa
        check("output loads", False, str(e))

    stage("4. Cross-tool contracts")
    manifest = json.load(open(stem + ".json"))
    check("manifest records slots alignment",
          manifest.get("slots", {}).get("aligned") is True)
    check("manifest depth = lux", manifest.get("depth") == "lux",
          manifest.get("depth"))
    dressing = json.load(open(stem + ".dressing.json"))
    check("dressing schema", dressing.get("schema") == "patina-dressing/1")
    check("all covers non-collision",
          all(o.get("collision") == "none" for o in dressing.get("orders", [])),
          f"{len(dressing.get('orders', []))} orders")
    check("dressing in Blender space", "Blender" in dressing.get("space", ""))
    instances = json.load(open(stem + ".instances.json"))
    check("instances schema", instances.get("schema") == "patina-instances/1")
    check("per-slot instances present", instances.get("count", 0) > 0,
          f"{instances.get('count')} instances")

    if zoo_repo:
        try:
            sys.path.insert(0, zoo_repo)
            from zoo_keeper.core import dressing as zdress
            genome = json.load(open(os.path.join(
                zoo_repo, "zoo_keeper", "genome", "species", "dress_cover.json")))
            plan = zdress.plan_dressing(dressing, genome, "delco", "smoke")
            check("Zoo planner accepts dressing",
                  plan["cover_count"] == len(dressing["orders"]),
                  f"{plan['cover_count']} covers planned")
            check("Zoo drops nothing unexpectedly",
                  plan["cover_count"] > 0)
        except Exception as e:                   # noqa
            check("Zoo dressing planner", False, str(e))
    else:
        print("  [skip] Zoo planner (pass --zoo <repo> to check)")

    stage("5. Composite headroom")
    hz = [ln for ln in proc.stdout.splitlines() if "luma mean" in ln]
    check("preview reported headroom", bool(hz), hz[0].strip() if hz else "")
    check("headroom OK (not too dark)",
          bool(hz) and "TOO DARK" not in hz[0], hz[0].strip() if hz else "")

    print("\n" + "=" * 52)
    if _fails:
        print(f"SMOKE TEST FAILED — {len(_fails)} check(s): {', '.join(_fails)}")
        return 1
    print("SMOKE TEST PASSED — the offline pipeline holds end to end.")
    print("Next: the Blender/Godot walk (smoke_walk.ps1) for the in-engine half.")
    return 0


def _patina_repo() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return here if os.path.isdir(os.path.join(here, "patina")) else here


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("build_dir", help="Deli Counter build dir with <name>.slots.json + .glb")
    ap.add_argument("--zoo", help="Zoo repo root (to also check the dressing planner)")
    args = ap.parse_args()
    print("Pipeline smoke test (offline stages)")
    print(f"  build dir: {args.build_dir}")
    return run(args.build_dir, args.zoo)


if __name__ == "__main__":
    raise SystemExit(main())
