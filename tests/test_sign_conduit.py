"""A sign is not a conduit target (0.29.2).

Roadmap 220. Deli Counter stands a sign's light anchor on the sign's FACE, `_SIGN_OUT` (0.2 m)
proud of the wall, and hangs every sign it derives over a door. A conduit run "from the ground up
to the fixture" stood there, 0.2 m out in the air, and `openings.apply`, starting it above the
door head, left a 0.27 m stub from the head to the middle of the lit face, standing through it.
Walked as a light bar on strip_club_a01's door sign in cold runs 9213 and 9217, and ordered on
all three signed buildings of club_block_014. A cabinet sign is fed through the wall behind it.
"""
import numpy as np

from patina import anchors, openings
from patina.mesh import Scene

#: strip_club_a01 in cold run 9217, spec frame: the door sign's anchor on its face plane, the
#: north door's wall pack, and the south door the sign hangs over
_SIGN = {"id": "ext_0_S_sign", "type": "sign", "pos": [-5.0, -12.35, 2.55]}
_PACK = {"id": "ext_0_N_pack_1", "type": "wall_pack", "pos": [-10.0, 12.3, 2.45]}


def _lights(*anchors_):
    return {"light_manifest_version": "1.1.0", "anchors": list(anchors_)}


def _south_wall():
    """strip_club_a01's south wall in Patina's canonical frame, where y is the spec's negated.

    Its normal is OUTWARD, +y here, since the south face looks to the spec's -y (0.30.0). 0.29.2
    wrote -y: the inward normal the anchor pass then derived for every wall (roadmap 221)."""
    return {"axis": 1, "along": 0, "normal": np.array([0.0, 1.0]), "fixed": 12.0,
            "a_min": -17.0, "a_max": 17.0, "z_lo": 0.0, "z_hi": 3.3}


def _generate(segs, opts):
    real = anchors._wall_segments
    anchors._wall_segments = lambda scene, **_k: iter(segs)
    try:
        return anchors._generate_zup(Scene(), opts, 1999)
    finally:
        anchors._wall_segments = real


def test_a_sign_is_not_a_conduit_target():
    assert anchors.conduit_targets(_lights(_SIGN), 1) == ()


def test_a_wall_pack_still_is():
    got = anchors.conduit_targets(_lights(_PACK, _SIGN), 1)
    assert [t[1] for t in got] == ["ext_0_N_pack_1"]


def test_the_signed_door_orders_no_stub_through_the_face():
    """End to end at the order level: the sign over the south door makes no conduit, so the
    opening pass has nothing to shorten into a stub. On 0.29.1 this ordered one conduit, which
    `openings.apply` cut to 0.27 m above the 2.28 m door head -- the bar."""
    opts = anchors.AnchorOptions(ground_z=0.0, kinds=("exterior_light",),
                                 conduit_targets=anchors.conduit_targets(_lights(_SIGN), 1))
    out = _generate([_south_wall()], opts)
    assert [a for a in out if a.kind == "exterior_light"] == []


def test_the_old_stub_was_what_the_bar_measured():
    """The instrument for the claim above, kept: the order 0.29.1 made for this sign, through
    the opening pass, is the 0.27 m stub on the face plane that cold run 9217 shipped."""
    target = ((anchors.blender_to_canonical(_SIGN["pos"], 1), _SIGN["id"]),)
    opts = anchors.AnchorOptions(ground_z=0.0, kinds=("exterior_light",), conduit_targets=target)
    (a,) = _generate([_south_wall()], opts)
    order = {"cover": "conduit_run", "pos": [a.pos[0], -a.pos[1], a.pos[2]], "size": a.size,
             "normal": list(a.normal)}
    door = {"slot_id": "ext_0_S_open0", "x0": -5.88, "x1": -4.12, "y0": -13.0, "y1": -11.0,
            "z0": -0.08, "z1": 2.28}
    kept, report = openings.apply([order], [door])
    assert report["shortened"] == {"conduit_run": 1}
    (stub,) = kept
    assert stub["size"] == 0.27
    # 0.30.0 stands a conduit on its wall's plane, -12.0 here. 0.29.1 stood this one where the
    # sign's anchor was, on its face plane at -12.35, 0.2 m off the wall: what 9217 shipped.
    assert stub["pos"][1] == -12.0
