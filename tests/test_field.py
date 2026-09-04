from features.field import GOAL_Y, own_goal_location


def test_team_0_defends_negative_y():
    assert own_goal_location(0) == {"x": 0.0, "y": -GOAL_Y, "z": 0.0}


def test_team_1_defends_positive_y():
    assert own_goal_location(1) == {"x": 0.0, "y": GOAL_Y, "z": 0.0}
