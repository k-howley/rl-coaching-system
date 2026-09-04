"""Fuzzy positional-exposure detector.

features/positioning.py deliberately leaves distance_to_own_goal,
ball_threat_to_own_goal and has_teammate_covering as separate crisp signals.
This module is where they actually get combined, via a Mamdani fuzzy
inference system (scikit-fuzzy) rather than a hand-coded formula — this is
the "fuzzy" part of the fuzzy detector.

Implemented directly with skfuzzy's low-level interp_membership/defuzz
primitives rather than skfuzzy.control's Antecedent/Consequent/Rule/
ControlSystemSimulation classes. Measured: the high-level API costs ~10ms per
call regardless of its own input cache, because that cache stores every seen
input in a plain list and checks membership with a linear `in` scan — real
replay data is virtually never the same value twice, so every call is a cache
miss anyway, and the scan cost grows as the list does. At ~66k calls per
replay (frames x players) that's minutes, not seconds. The direct
implementation below computes the exact same Mamdani inference (per-term
membership -> per-rule AND (min) firing strength -> per-consequent-term OR
(max) aggregation -> centroid defuzzification) in ~0.05ms/call, roughly 200x
faster, with no cache to grow at all.

The rule table is a complete 3x3x2 grid (distance x ball_threat x covering),
built programmatically so every input combination is guaranteed to fire at
least one rule — an incomplete table would silently zero out the aggregate
membership for some real inputs instead of just producing a bad score.
"""

import numpy as np
import skfuzzy as fuzz

from features.field import FIELD_LENGTH

_DIST_UNIVERSE = np.linspace(0, FIELD_LENGTH, 101)
_THREAT_UNIVERSE = np.linspace(0, 1, 101)
_COVERED_UNIVERSE = np.linspace(0, 1, 101)
_EXPOSURE_UNIVERSE = np.linspace(0, 100, 101)

_DIST_TERMS = {
    "close": fuzz.trimf(_DIST_UNIVERSE, [0, 0, FIELD_LENGTH / 2]),
    "medium": fuzz.trimf(_DIST_UNIVERSE, [0, FIELD_LENGTH / 2, FIELD_LENGTH]),
    "far": fuzz.trimf(_DIST_UNIVERSE, [FIELD_LENGTH / 2, FIELD_LENGTH, FIELD_LENGTH]),
}
_THREAT_TERMS = {
    "low": fuzz.trimf(_THREAT_UNIVERSE, [0, 0, 0.5]),
    "medium": fuzz.trimf(_THREAT_UNIVERSE, [0, 0.5, 1]),
    "high": fuzz.trimf(_THREAT_UNIVERSE, [0.5, 1, 1]),
}
# has_teammate_covering is a crisp bool fed in as 0.0/1.0; these two sets are
# just linear complements of each other so a crisp input still maps cleanly.
_COVERED_TERMS = {
    "no": fuzz.trimf(_COVERED_UNIVERSE, [0, 0, 1]),
    "yes": fuzz.trimf(_COVERED_UNIVERSE, [0, 1, 1]),
}
_EXPOSURE_TERMS = {
    "low": fuzz.trimf(_EXPOSURE_UNIVERSE, [0, 0, 50]),
    "medium": fuzz.trimf(_EXPOSURE_UNIVERSE, [0, 50, 100]),
    "high": fuzz.trimf(_EXPOSURE_UNIVERSE, [50, 100, 100]),
}

# Complete decision table: (distance, ball_threat, teammate_covering) -> exposure.
# Intuition: low ball threat or being close to goal yourself is always safe
# (you/nobody needs covering). Once distance is medium/far AND the ball is
# genuinely threatening, having a teammate goal-side of you halves the risk.
_DECISION_TABLE = {
    ("close", "low", "no"): "low",
    ("close", "low", "yes"): "low",
    ("close", "medium", "no"): "low",
    ("close", "medium", "yes"): "low",
    ("close", "high", "no"): "low",
    ("close", "high", "yes"): "low",
    ("medium", "low", "no"): "low",
    ("medium", "low", "yes"): "low",
    ("medium", "medium", "no"): "medium",
    ("medium", "medium", "yes"): "low",
    ("medium", "high", "no"): "high",
    ("medium", "high", "yes"): "medium",
    ("far", "low", "no"): "low",
    ("far", "low", "yes"): "low",
    ("far", "medium", "no"): "medium",
    ("far", "medium", "yes"): "low",
    ("far", "high", "no"): "high",
    ("far", "high", "yes"): "medium",
}


def _memberships(value: float, universe: np.ndarray, terms: dict) -> dict:
    return {name: fuzz.interp_membership(universe, mf, value) for name, mf in terms.items()}


def exposure_score(distance_to_own_goal: float, ball_threat: float, has_teammate_covering: bool) -> float:
    """0-100 fuzzy positional-exposure score for one player at one frame."""
    distance_to_own_goal = min(max(distance_to_own_goal, 0.0), FIELD_LENGTH)
    ball_threat = min(max(ball_threat, 0.0), 1.0)
    covered_value = 1.0 if has_teammate_covering else 0.0

    dist_membership = _memberships(distance_to_own_goal, _DIST_UNIVERSE, _DIST_TERMS)
    threat_membership = _memberships(ball_threat, _THREAT_UNIVERSE, _THREAT_TERMS)
    covered_membership = _memberships(covered_value, _COVERED_UNIVERSE, _COVERED_TERMS)

    aggregate = np.zeros_like(_EXPOSURE_UNIVERSE)
    for (dist_term, threat_term, covered_term), exposure_term in _DECISION_TABLE.items():
        firing_strength = min(
            dist_membership[dist_term],
            threat_membership[threat_term],
            covered_membership[covered_term],
        )
        clipped = np.fmin(firing_strength, _EXPOSURE_TERMS[exposure_term])
        aggregate = np.fmax(aggregate, clipped)

    if not aggregate.any():
        return 0.0
    return float(fuzz.defuzz(_EXPOSURE_UNIVERSE, aggregate, "centroid"))
