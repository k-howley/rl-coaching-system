from parser.actor_tracker import ActorRegistry, iter_snapshots

OBJECTS = [
    "TAGame.Default__PRI_TA",  # 0
    "Archetypes.Car.Car_Default",  # 1
    "Archetypes.Ball.Ball_Default",  # 2
    "Archetypes.Teams.Team0",  # 3
    "Archetypes.CarComponents.CarComponent_Boost",  # 4
    "Engine.Pawn:PlayerReplicationInfo",  # 5
    "Engine.PlayerReplicationInfo:PlayerName",  # 6
    "Engine.PlayerReplicationInfo:Team",  # 7
    "TAGame.RBActor_TA:ReplicatedRBState",  # 8
    "TAGame.CarComponent_TA:Vehicle",  # 9
    "TAGame.CarComponent_Boost_TA:ReplicatedBoost",  # 10
    "TAGame.CarComponent_Boost_TA:ReplicatedBoostAmount",  # 11
]


def rigid_body(x: float) -> dict:
    return {
        "sleeping": False,
        "location": {"x": x, "y": 0.0, "z": 17.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        "linear_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
    }


def boost(amount: int) -> dict:
    return {"grant_count": 0, "boost_amount": amount, "unused1": 0, "unused2": 0}


def active_actor(actor_id: int) -> dict:
    return {"ActiveActor": {"active": True, "actor": actor_id}}


def inactive_actor() -> dict:
    """Unreal's idiom for "this reference is temporarily unset" — actor is
    always -1 alongside active: False. Real replays send this briefly during
    a car respawn transition before re-linking to the (same) PRI."""
    return {"ActiveActor": {"active": False, "actor": -1}}


def test_resolves_player_car_team_and_boost():
    frame = {
        "time": 1.0,
        "delta": 0.033,
        "new_actors": [
            {"actor_id": 1, "name_id": 0, "object_id": 0, "initial_trajectory": {}},  # PRI
            {"actor_id": 2, "name_id": 1, "object_id": 1, "initial_trajectory": {}},  # car
            {"actor_id": 3, "name_id": 2, "object_id": 2, "initial_trajectory": {}},  # ball
            {"actor_id": 4, "name_id": 3, "object_id": 3, "initial_trajectory": {}},  # team0
            {"actor_id": 5, "name_id": 4, "object_id": 4, "initial_trajectory": {}},  # boost component
        ],
        "deleted_actors": [],
        "updated_actors": [
            {"actor_id": 2, "stream_id": 1, "object_id": 5, "attribute": active_actor(1)},
            {"actor_id": 1, "stream_id": 2, "object_id": 6, "attribute": {"String": "Ari"}},
            {"actor_id": 1, "stream_id": 3, "object_id": 7, "attribute": active_actor(4)},
            {"actor_id": 2, "stream_id": 4, "object_id": 8, "attribute": {"RigidBody": rigid_body(100.0)}},
            {"actor_id": 3, "stream_id": 5, "object_id": 8, "attribute": {"RigidBody": rigid_body(0.0)}},
            {"actor_id": 5, "stream_id": 6, "object_id": 9, "attribute": active_actor(2)},
            {"actor_id": 5, "stream_id": 7, "object_id": 10, "attribute": {"ReplicatedBoost": boost(100)}},
        ],
    }

    registry = ActorRegistry(objects=OBJECTS)
    registry.apply_frame(frame)
    snapshot = registry.snapshot()

    assert snapshot["time"] == 1.0
    assert len(snapshot["players"]) == 1
    player = snapshot["players"][0]
    assert player["player_name"] == "Ari"
    assert player["team"] == 0
    assert player["car_actor_id"] == 2
    assert player["rigid_body"]["location"]["x"] == 100.0
    assert player["boost_amount"] == 100
    assert snapshot["ball"]["location"]["x"] == 0.0


def test_survives_car_respawn_with_new_actor_id():
    """A demolished car gets a brand new actor_id; the player must still resolve."""
    frame_1 = {
        "time": 1.0,
        "delta": 0.033,
        "new_actors": [
            {"actor_id": 1, "name_id": 0, "object_id": 0, "initial_trajectory": {}},  # PRI
            {"actor_id": 2, "name_id": 1, "object_id": 1, "initial_trajectory": {}},  # car (v1)
            {"actor_id": 5, "name_id": 4, "object_id": 4, "initial_trajectory": {}},  # boost component (v1)
        ],
        "deleted_actors": [],
        "updated_actors": [
            {"actor_id": 2, "stream_id": 1, "object_id": 5, "attribute": active_actor(1)},
            {"actor_id": 1, "stream_id": 2, "object_id": 6, "attribute": {"String": "Ari"}},
            {"actor_id": 2, "stream_id": 3, "object_id": 8, "attribute": {"RigidBody": rigid_body(100.0)}},
            {"actor_id": 5, "stream_id": 4, "object_id": 9, "attribute": active_actor(2)},
            {"actor_id": 5, "stream_id": 5, "object_id": 10, "attribute": {"ReplicatedBoost": boost(100)}},
        ],
    }
    frame_2 = {
        "time": 2.0,
        "delta": 0.033,
        "new_actors": [
            {"actor_id": 6, "name_id": 1, "object_id": 1, "initial_trajectory": {}},  # car (v2, demolished+respawned)
            {"actor_id": 7, "name_id": 4, "object_id": 4, "initial_trajectory": {}},  # boost component (v2)
        ],
        "deleted_actors": [2, 5],
        "updated_actors": [
            {"actor_id": 6, "stream_id": 1, "object_id": 5, "attribute": active_actor(1)},
            {"actor_id": 6, "stream_id": 2, "object_id": 8, "attribute": {"RigidBody": rigid_body(200.0)}},
            {"actor_id": 7, "stream_id": 3, "object_id": 9, "attribute": active_actor(6)},
            {"actor_id": 7, "stream_id": 4, "object_id": 10, "attribute": {"ReplicatedBoost": boost(33)}},
        ],
    }

    registry = ActorRegistry(objects=OBJECTS)
    registry.apply_frame(frame_1)
    registry.apply_frame(frame_2)
    snapshot = registry.snapshot()

    assert len(snapshot["players"]) == 1
    player = snapshot["players"][0]
    assert player["player_name"] == "Ari"
    assert player["car_actor_id"] == 6
    assert player["rigid_body"]["location"]["x"] == 200.0
    assert player["boost_amount"] == 33

    # stale actor_ids must not linger anywhere in the registry
    assert 2 not in registry.rigid_body
    assert 5 not in registry.boost_component_to_car


def test_boost_survives_component_channel_recycle_with_no_new_value():
    """Real behavior observed in actual replays: the boost component actor
    gets deleted and replaced with a new actor_id periodically as part of a
    replication channel recycle, unrelated to any real gameplay event (the
    car itself is untouched). If no new ReplicatedBoost value ever arrives
    for the replacement component, the last known boost amount must still be
    reported rather than going None."""
    frame_1 = {
        "time": 1.0,
        "delta": 0.033,
        "new_actors": [
            {"actor_id": 1, "name_id": 0, "object_id": 0, "initial_trajectory": {}},  # PRI
            {"actor_id": 2, "name_id": 1, "object_id": 1, "initial_trajectory": {}},  # car
            {"actor_id": 5, "name_id": 4, "object_id": 4, "initial_trajectory": {}},  # boost component (v1)
        ],
        "deleted_actors": [],
        "updated_actors": [
            {"actor_id": 2, "stream_id": 1, "object_id": 5, "attribute": active_actor(1)},
            {"actor_id": 1, "stream_id": 2, "object_id": 6, "attribute": {"String": "Ari"}},
            {"actor_id": 2, "stream_id": 3, "object_id": 8, "attribute": {"RigidBody": rigid_body(100.0)}},
            {"actor_id": 5, "stream_id": 4, "object_id": 9, "attribute": active_actor(2)},
            {"actor_id": 5, "stream_id": 5, "object_id": 10, "attribute": {"ReplicatedBoost": boost(70)}},
        ],
    }
    frame_2 = {
        "time": 2.0,
        "delta": 0.033,
        # boost component (v1) is deleted and replaced by a new one (v2),
        # but the car (actor 2) is untouched, and no ReplicatedBoost update
        # ever arrives for the new component in this frame.
        "new_actors": [
            {"actor_id": 9, "name_id": 4, "object_id": 4, "initial_trajectory": {}},  # boost component (v2)
        ],
        "deleted_actors": [5],
        "updated_actors": [
            {"actor_id": 9, "stream_id": 1, "object_id": 9, "attribute": active_actor(2)},
        ],
    }

    registry = ActorRegistry(objects=OBJECTS)
    registry.apply_frame(frame_1)
    registry.apply_frame(frame_2)
    snapshot = registry.snapshot()

    assert len(snapshot["players"]) == 1
    player = snapshot["players"][0]
    assert player["car_actor_id"] == 2
    assert player["boost_amount"] == 70  # last known value, not None


def test_boost_amount_via_byte_variant_property():
    """Some real replays only ever send ReplicatedBoostAmount (a plain byte)
    instead of the composite ReplicatedBoost struct."""
    frame = {
        "time": 1.0,
        "delta": 0.033,
        "new_actors": [
            {"actor_id": 1, "name_id": 0, "object_id": 0, "initial_trajectory": {}},  # PRI
            {"actor_id": 2, "name_id": 1, "object_id": 1, "initial_trajectory": {}},  # car
            {"actor_id": 5, "name_id": 4, "object_id": 4, "initial_trajectory": {}},  # boost component
        ],
        "deleted_actors": [],
        "updated_actors": [
            {"actor_id": 2, "stream_id": 1, "object_id": 5, "attribute": active_actor(1)},
            {"actor_id": 1, "stream_id": 2, "object_id": 6, "attribute": {"String": "Ari"}},
            {"actor_id": 5, "stream_id": 3, "object_id": 9, "attribute": active_actor(2)},
            {"actor_id": 5, "stream_id": 4, "object_id": 11, "attribute": {"Byte": 85}},
        ],
    }

    registry = ActorRegistry(objects=OBJECTS)
    registry.apply_frame(frame)
    snapshot = registry.snapshot()

    assert snapshot["players"][0]["boost_amount"] == 85


def test_pawn_pri_link_ignores_transient_inactive_update():
    """Real bug found against actual replay data: a car's
    Engine.Pawn:PlayerReplicationInfo briefly sends {active: False, actor: -1}
    during a respawn transition. Blindly overwriting car_to_pri with -1 broke
    name/team resolution for that player until the next valid link update —
    which sometimes took seconds, showing up as tips attributed to "None"."""
    frame_1 = {
        "time": 1.0,
        "delta": 0.033,
        "new_actors": [
            {"actor_id": 1, "name_id": 0, "object_id": 0, "initial_trajectory": {}},  # PRI
            {"actor_id": 2, "name_id": 1, "object_id": 1, "initial_trajectory": {}},  # car
        ],
        "deleted_actors": [],
        "updated_actors": [
            {"actor_id": 2, "stream_id": 1, "object_id": 5, "attribute": active_actor(1)},
            {"actor_id": 1, "stream_id": 2, "object_id": 6, "attribute": {"String": "Ari"}},
            {"actor_id": 2, "stream_id": 3, "object_id": 8, "attribute": {"RigidBody": rigid_body(100.0)}},
        ],
    }
    frame_2 = {
        "time": 2.0,
        "delta": 0.033,
        "new_actors": [],
        "deleted_actors": [],
        "updated_actors": [
            # link briefly clears during respawn transition; car_actor_id and
            # pri_actor_id are unchanged, no new_actors/deleted_actors at all
            {"actor_id": 2, "stream_id": 4, "object_id": 5, "attribute": inactive_actor()},
        ],
    }

    registry = ActorRegistry(objects=OBJECTS)
    registry.apply_frame(frame_1)
    registry.apply_frame(frame_2)
    snapshot = registry.snapshot()

    assert len(snapshot["players"]) == 1
    assert snapshot["players"][0]["player_name"] == "Ari"
    assert snapshot["players"][0]["car_actor_id"] == 2


def test_iter_snapshots_yields_one_per_frame():
    replay = {
        "objects": OBJECTS,
        "network_frames": {
            "frames": [
                {"time": 0.0, "delta": 0.0, "new_actors": [], "deleted_actors": [], "updated_actors": []},
                {"time": 0.033, "delta": 0.033, "new_actors": [], "deleted_actors": [], "updated_actors": []},
            ]
        },
    }

    snapshots = list(iter_snapshots(replay))

    assert [s["time"] for s in snapshots] == [0.0, 0.033]
    assert all(s["players"] == [] and s["ball"] is None for s in snapshots)
