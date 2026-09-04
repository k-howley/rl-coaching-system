import numpy as np
import pytest

from detectors.exposure import exposure_score
from features.field import FIELD_LENGTH


def test_close_to_goal_is_always_low_exposure_regardless_of_threat():
    for threat in (0.0, 0.5, 1.0):
        for covered in (False, True):
            score = exposure_score(0.0, threat, covered)
            assert score < 30, (threat, covered, score)


def test_low_ball_threat_is_always_low_exposure_regardless_of_distance():
    for distance in (0.0, FIELD_LENGTH / 2, FIELD_LENGTH):
        for covered in (False, True):
            score = exposure_score(distance, 0.0, covered)
            assert score < 30, (distance, covered, score)


def test_far_and_high_threat_and_uncovered_is_high_exposure():
    score = exposure_score(FIELD_LENGTH, 1.0, has_teammate_covering=False)
    assert score > 70


def test_teammate_covering_reduces_exposure_for_same_distance_and_threat():
    uncovered = exposure_score(FIELD_LENGTH, 1.0, has_teammate_covering=False)
    covered = exposure_score(FIELD_LENGTH, 1.0, has_teammate_covering=True)
    assert covered < uncovered


def test_exposure_is_monotonic_in_ball_threat_when_far_and_uncovered():
    scores = [exposure_score(FIELD_LENGTH, threat, False) for threat in np.linspace(0, 1, 11)]
    assert all(a <= b + 1e-6 for a, b in zip(scores, scores[1:]))


@pytest.mark.parametrize("distance", np.linspace(0, FIELD_LENGTH, 7))
@pytest.mark.parametrize("threat", np.linspace(0, 1, 7))
@pytest.mark.parametrize("covered", [False, True])
def test_full_input_grid_never_raises_and_stays_in_range(distance, threat, covered):
    """Regression guard for the rule-coverage gap: an incomplete decision
    table causes scikit-fuzzy to raise a KeyError on defuzzification for
    some inputs instead of returning a score."""
    score = exposure_score(distance, threat, covered)
    assert 0.0 <= score <= 100.0
