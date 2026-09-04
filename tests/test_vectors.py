from features.vectors import distance, magnitude


def test_magnitude():
    assert magnitude({"x": 3.0, "y": 4.0, "z": 0.0}) == 5.0


def test_magnitude_zero_vector():
    assert magnitude({"x": 0.0, "y": 0.0, "z": 0.0}) == 0.0


def test_distance():
    a = {"x": 0.0, "y": 0.0, "z": 0.0}
    b = {"x": 3.0, "y": 4.0, "z": 0.0}
    assert distance(a, b) == 5.0


def test_distance_is_symmetric():
    a = {"x": 1.0, "y": 2.0, "z": 3.0}
    b = {"x": -4.0, "y": 5.0, "z": 6.0}
    assert distance(a, b) == distance(b, a)
