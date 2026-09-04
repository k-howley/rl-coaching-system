import math

from features.kinematics import boost_percent, is_upside_down, speed, uprightness


def rigid_body(velocity=None, rotation=None):
    return {
        "sleeping": velocity is None,
        "location": {"x": 0.0, "y": 0.0, "z": 17.0},
        "rotation": rotation or {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        "linear_velocity": velocity,
        "angular_velocity": velocity,
    }


def test_speed_none_when_body_missing():
    assert speed(None) is None


def test_speed_none_when_sleeping():
    assert speed(rigid_body(velocity=None)) is None


def test_speed_magnitude():
    body = rigid_body(velocity={"x": 3.0, "y": 4.0, "z": 0.0})
    assert speed(body) == 5.0


def test_boost_percent_range():
    assert boost_percent(None) is None
    assert boost_percent(0) == 0.0
    assert boost_percent(255) == 100.0
    assert round(boost_percent(85), 2) == round((85 / 255) * 100, 2)


def test_uprightness_identity_quaternion_is_upright():
    body = rigid_body(velocity={"x": 0.0, "y": 0.0, "z": 0.0})
    assert uprightness(body) == 1.0


def test_uprightness_180_flip_about_x_is_upside_down():
    body = rigid_body(
        velocity={"x": 0.0, "y": 0.0, "z": 0.0},
        rotation={"x": 1.0, "y": 0.0, "z": 0.0, "w": 0.0},
    )
    assert uprightness(body) == -1.0
    assert is_upside_down(body) is True


def test_uprightness_90_degrees_is_on_its_side():
    half_sqrt2 = math.sqrt(2) / 2
    body = rigid_body(
        velocity={"x": 0.0, "y": 0.0, "z": 0.0},
        rotation={"x": half_sqrt2, "y": 0.0, "z": 0.0, "w": half_sqrt2},
    )
    # exactly 0.0 in theory; floating-point rounding puts it right on the
    # is_upside_down boundary, so only assert the value itself here
    assert round(uprightness(body), 6) == 0.0


def test_uprightness_none_when_body_missing():
    assert uprightness(None) is None
    assert is_upside_down(None) is None
