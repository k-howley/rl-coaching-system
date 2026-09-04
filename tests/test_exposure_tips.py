from coaching.exposure_tips import (
    ExposurePoint,
    build_exposure_timeline,
    find_incidents,
    format_tip,
    generate_tips,
)
from features.field import GOAL_Y


def point(time, score, distance=8000.0, threat=0.9):
    return ExposurePoint(time=time, score=score, distance_to_own_goal=distance, ball_threat=threat)


def test_find_incidents_groups_consecutive_points_above_threshold():
    points = [point(t, 80.0) for t in range(10)]
    incidents = find_incidents(points, threshold=50.0, min_frames=5)
    assert len(incidents) == 1
    assert incidents[0].start_time == 0
    assert incidents[0].end_time == 9
    assert incidents[0].frame_count == 10


def test_find_incidents_drops_runs_shorter_than_min_frames():
    points = [point(t, 80.0) for t in range(3)]  # only 3 frames
    incidents = find_incidents(points, threshold=50.0, min_frames=5)
    assert incidents == []


def test_find_incidents_splits_separate_runs():
    points = (
        [point(t, 80.0) for t in range(0, 10)]
        + [point(t, 10.0) for t in range(10, 20)]  # drops below threshold
        + [point(t, 90.0) for t in range(20, 30)]
    )
    incidents = find_incidents(points, threshold=50.0, min_frames=5)
    assert len(incidents) == 2
    assert incidents[0].start_time == 0
    assert incidents[0].end_time == 9
    assert incidents[1].start_time == 20
    assert incidents[1].end_time == 29


def test_find_incidents_closes_a_run_still_active_at_the_end():
    points = [point(t, 80.0) for t in range(10)]  # never drops below threshold
    incidents = find_incidents(points, threshold=50.0, min_frames=5)
    assert len(incidents) == 1
    assert incidents[0].end_time == 9


def test_find_incidents_peak_is_the_max_scoring_point_in_the_run():
    points = [point(0, 60.0), point(1, 95.0), point(2, 70.0)]
    incidents = find_incidents(points, threshold=50.0, min_frames=1)
    assert incidents[0].peak_score == 95.0


def test_format_tip_includes_timestamp_and_stats():
    incident = find_incidents([point(t, 80.0, distance=7500.0, threat=0.85) for t in range(65, 95)], min_frames=5)[0]
    # start_time is the integer 65 here (seconds), formatted as m:ss
    text = format_tip(incident)
    assert "1:05" in text
    assert "7500" in text
    assert "85%" in text


def rigid_body(x=0.0, y=0.0, z=0.0, velocity=(0.0, 0.0, 0.0)):
    return {
        "sleeping": False,
        "location": {"x": x, "y": y, "z": z},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        "linear_velocity": {"x": velocity[0], "y": velocity[1], "z": velocity[2]},
        "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
    }


def snapshot_at(time, player_y, ball_y):
    return {
        "time": time,
        "ball": rigid_body(y=ball_y),
        "players": [
            {
                "player_name": "Solo",
                "team": 0,
                "car_actor_id": 1,
                "rigid_body": rigid_body(y=player_y),
                "boost_amount": 100,
            }
        ],
    }


def test_build_exposure_timeline_scores_every_frame_for_a_lone_player():
    snapshots = [snapshot_at(float(i), player_y=4000.0, ball_y=-5000.0) for i in range(5)]
    timelines = build_exposure_timeline(snapshots)
    assert list(timelines.keys()) == ["Solo"]
    assert len(timelines["Solo"]) == 5


def test_build_exposure_timeline_skips_players_without_a_body():
    snapshot = snapshot_at(0.0, player_y=4000.0, ball_y=-5000.0)
    snapshot["players"][0]["rigid_body"] = None
    timelines = build_exposure_timeline([snapshot])
    assert timelines == {}


def test_generate_tips_end_to_end_flags_a_sustained_exposure():
    # Solo player parked far upfield (near +GOAL_Y, i.e. far from their own
    # -GOAL_Y goal) with no teammate, ball sitting on their own goal line the
    # whole time -> high, sustained exposure.
    snapshots = [
        snapshot_at(i * 0.1, player_y=GOAL_Y - 500.0, ball_y=-GOAL_Y) for i in range(40)
    ]
    tips = generate_tips(snapshots, threshold=50.0, min_frames=10)
    assert "Solo" in tips
    assert len(tips["Solo"]) == 1
    assert "out of position" in tips["Solo"][0]


def test_generate_tips_empty_when_never_exposed():
    # Player camped right on their own goal line -> always "close", never exposed.
    snapshots = [snapshot_at(i * 0.1, player_y=-GOAL_Y, ball_y=-GOAL_Y) for i in range(40)]
    tips = generate_tips(snapshots, threshold=50.0, min_frames=10)
    assert tips == {}
