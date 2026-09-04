from features.field import GOAL_Y
from features.positioning import ball_threat_to_goal, distance_to_own_goal, has_teammate_covering


def body_at(x=0.0, y=0.0, z=0.0):
    return {"location": {"x": x, "y": y, "z": z}}


def player(name, team, y, has_body=True):
    return {"player_name": name, "team": team, "rigid_body": body_at(y=y) if has_body else None}


def test_distance_to_own_goal_zero_at_goal_line():
    assert distance_to_own_goal(body_at(y=-GOAL_Y), team=0) == 0.0


def test_ball_threat_max_at_own_goal_line():
    assert ball_threat_to_goal(body_at(y=-GOAL_Y), team=0) == 1.0


def test_ball_threat_zero_at_far_goal_line():
    assert ball_threat_to_goal(body_at(y=GOAL_Y), team=0) == 0.0


def test_ball_threat_none_without_ball():
    assert ball_threat_to_goal(None, team=0) is None


def test_has_teammate_covering_true_for_the_more_forward_player():
    last_man = player("A", team=0, y=-4000.0)  # close to team 0's goal (-GOAL_Y)
    forward_player = player("B", team=0, y=2000.0)  # far forward
    players = [last_man, forward_player]

    assert has_teammate_covering(forward_player, players) is True
    assert has_teammate_covering(last_man, players) is False


def test_has_teammate_covering_ignores_opponents():
    lone_player = player("A", team=0, y=0.0)
    opponent = player("B", team=1, y=-5000.0)  # would be "covering" if teams were ignored

    assert has_teammate_covering(lone_player, [lone_player, opponent]) is False


def test_has_teammate_covering_none_without_own_body():
    bodyless = player("A", team=0, y=0.0, has_body=False)
    teammate = player("B", team=0, y=-1000.0)

    assert has_teammate_covering(bodyless, [bodyless, teammate]) is None
