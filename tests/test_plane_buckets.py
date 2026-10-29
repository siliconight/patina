"""One plane is one bucket, whichever side of a rounding boundary its float lands (0.33.1).

Measured on Deli Counter 0.292.0's `bank_branch_a02`, whose parapet stands flush on its facade: the facade's faces at
y 11.149998664855957 and the parapet's at 11.15000057220459, which `round(_, 1)` sent to 11.1 and 11.2 -- two
segments, the facade's topping out at 6.9 m, and 24 roofline strips across a flat wall
(the factory's docs/findings/parapet_flush/, bucket_probe.py).
"""
from patina import anchors

FACADE, PARAPET = 11.149998664855957, 11.15000057220459


def _faces(*planes, axis=1, side="hi"):
    return [(axis, side, p, None, None, 0.0, 1.0) for p in planes]


def test_a_plane_split_by_float_noise_is_one_bucket():
    """FAILS ON 0.33.0: there was no clustering, and the two rounded apart."""
    keys = anchors._plane_keys(_faces(FACADE, PARAPET))
    assert keys[(1, "hi", FACADE)] == keys[(1, "hi", PARAPET)]
    assert round(FACADE, 1) != round(PARAPET, 1)          # the split this closes


def test_planes_a_real_distance_apart_bucket_as_they_did():
    """The control: every plane not within PLANE_TOL of another keeps
    round(plane, 1) -- the bank's 10.95 inner faces still share 11.0's bucket
    and the 15 cm wall still separates the face from its centre line."""
    ps = (11.0, 10.950000762939453, 11.149998664855957, -11.0, 15.2, 3.3333)
    keys = anchors._plane_keys(_faces(*ps))
    assert all(keys[(1, "hi", p)] == round(p, 1) for p in ps)


def test_sides_and_axes_never_cluster_together():
    keys = anchors._plane_keys(_faces(FACADE) + _faces(PARAPET, side="lo") + _faces(PARAPET, axis=0))
    assert keys[(1, "hi", FACADE)] == 11.1
    assert keys[(1, "lo", PARAPET)] == keys[(0, "hi", PARAPET)] == 11.2
