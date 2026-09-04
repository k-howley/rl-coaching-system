"""Team-relative positioning: who is covering the net, how threatened is it.

These are deliberately left as separate crisp signals (a distance, a threat
level, a boolean) rather than combined into one precomputed "exposure score" —
combining them with fuzzy membership functions/rules is the job of the
detectors/ layer, not feature engineering.
"""

from typing import Optional

from features.field import FIELD_LENGTH, own_goal_location
from features.vectors import distance


def distance_to_own_goal(rigid_body: dict, team: int) -> float:
    return distance(rigid_body["location"], own_goal_location(team))


def ball_threat_to_goal(ball_rigid_body: Optional[dict], team: int) -> Optional[float]:
    """0.0 (ball at the far end of the field) to 1.0 (ball on this team's goal line)."""
    if ball_rigid_body is None:
        return None
    goal_distance = distance_to_own_goal(ball_rigid_body, team)
    return max(0.0, min(1.0, 1.0 - goal_distance / FIELD_LENGTH))


def has_teammate_covering(player: dict, players: list[dict]) -> Optional[bool]:
    """True if some OTHER teammate is currently closer to the own goal than this player."""
    if player["rigid_body"] is None:
        return None
    own_distance = distance_to_own_goal(player["rigid_body"], player["team"])
    for teammate in players:
        if teammate is player or teammate["team"] != player["team"] or teammate["rigid_body"] is None:
            continue
        if distance_to_own_goal(teammate["rigid_body"], player["team"]) < own_distance:
            return True
    return False
