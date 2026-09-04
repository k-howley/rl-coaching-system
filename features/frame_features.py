"""Combines kinematics/positioning primitives into one feature dict per
player, per frame. Input is a single snapshot from
parser.actor_tracker.iter_snapshots()."""

from features.kinematics import boost_percent, speed, uprightness
from features.positioning import ball_threat_to_goal, distance_to_own_goal, has_teammate_covering
from features.vectors import distance


def player_features(player: dict, players: list[dict], ball: dict) -> dict:
    rigid_body = player["rigid_body"]
    return {
        "player_name": player["player_name"],
        "team": player["team"],
        "speed": speed(rigid_body),
        "boost_percent": boost_percent(player["boost_amount"]),
        "uprightness": uprightness(rigid_body),
        "distance_to_ball": distance(rigid_body["location"], ball["location"])
        if rigid_body and ball
        else None,
        "distance_to_own_goal": distance_to_own_goal(rigid_body, player["team"])
        if rigid_body
        else None,
        "ball_threat_to_own_goal": ball_threat_to_goal(ball, player["team"]),
        "has_teammate_covering": has_teammate_covering(player, players),
    }


def frame_features(snapshot: dict) -> dict:
    """snapshot -> {time, ball_speed, players: [player_features(), ...]}"""
    players = snapshot["players"]
    ball = snapshot["ball"]
    return {
        "time": snapshot["time"],
        "ball_speed": speed(ball),
        "players": [player_features(player, players, ball) for player in players],
    }
