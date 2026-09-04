from features.field import GOAL_Y
from features.frame_features import frame_features


def rigid_body(x=0.0, y=0.0, z=0.0, velocity=(0.0, 0.0, 0.0)):
    return {
        "sleeping": False,
        "location": {"x": x, "y": y, "z": z},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        "linear_velocity": {"x": velocity[0], "y": velocity[1], "z": velocity[2]},
        "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
    }


def test_frame_features_end_to_end():
    snapshot = {
        "time": 12.5,
        "ball": rigid_body(y=-4500.0, velocity=(0.0, -1000.0, 0.0)),
        "players": [
            {
                "player_name": "LastMan",
                "team": 0,
                "car_actor_id": 1,
                "rigid_body": rigid_body(y=-4000.0, velocity=(500.0, 0.0, 0.0)),
                "boost_amount": 255,
            },
            {
                "player_name": "Forward",
                "team": 0,
                "car_actor_id": 2,
                "rigid_body": rigid_body(y=2000.0, velocity=(0.0, 0.0, 0.0)),
                "boost_amount": 0,
            },
        ],
    }

    result = frame_features(snapshot)

    assert result["time"] == 12.5
    assert result["ball_speed"] == 1000.0
    assert len(result["players"]) == 2

    last_man, forward = result["players"]

    assert last_man["player_name"] == "LastMan"
    assert last_man["speed"] == 500.0
    assert last_man["boost_percent"] == 100.0
    assert last_man["has_teammate_covering"] is False
    assert last_man["distance_to_own_goal"] == 1120.0  # |-4000 - (-5120)|

    assert forward["player_name"] == "Forward"
    assert forward["speed"] == 0.0
    assert forward["boost_percent"] == 0.0
    assert forward["has_teammate_covering"] is True
    assert forward["distance_to_own_goal"] == 2000.0 + GOAL_Y

    # both teammates share the same team-relative ball threat
    assert last_man["ball_threat_to_own_goal"] == forward["ball_threat_to_own_goal"]
    assert last_man["ball_threat_to_own_goal"] > 0.5  # ball is near their own goal
