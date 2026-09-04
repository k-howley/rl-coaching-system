"""Resolves rrrocket's raw, reused actor_ids into stable per-player state.

rrrocket's network_frames stream only exposes short-lived actor_ids: a car,
its boost component, and each player's PlayerReplicationInfo (PRI) are all
separate actors linked together by reference properties, and actor_ids get
reused once an actor is deleted. This module walks the frame stream once,
keeping a live registry of those links, so callers can ask "what is player X
doing right now" instead of dealing with raw actor_ids.

Some low-priority components (observed: the boost component) also get
periodically deleted and replaced with a brand-new actor_id as part of a
replay-wide replication channel recycle, unrelated to any real gameplay event
(the car/PRI actors are unaffected by this and stay stable). Boost is
therefore anchored to the player's PRI actor_id rather than the transient
component's own actor_id, and is never cleared on that component's deletion —
only overwritten by a newer value. See docs/data_schema.md for how this was
diagnosed against real replay data.

Which boost property a replay actually uses also varies between real replay
files even at the same net_version: some use the composite
`TAGame.CarComponent_Boost_TA:ReplicatedBoost` struct, others only ever send
`TAGame.CarComponent_Boost_TA:ReplicatedBoostAmount` (a plain byte). Both are
handled.

`ActiveActor`-typed link properties (car->PRI, PRI->team, boost
component->car) can also send `{"active": False, "actor": -1}` — Unreal's
idiom for "this reference is temporarily unset", observed during a car
respawn transition. Blindly overwriting the mapping with actor -1 on these
updates corrupted name/team resolution for the affected player for however
long it took the next valid link to arrive (real impact: coaching tips
misattributed to a "None" player instead of the real one). These updates are
now ignored — the last known good mapping is kept — rather than accepted.

See docs/data_schema.md for how these property names were identified.
"""

from dataclasses import dataclass, field
from typing import Optional

PAWN_PRI_PROP = "Engine.Pawn:PlayerReplicationInfo"
PRI_NAME_PROP = "Engine.PlayerReplicationInfo:PlayerName"
PRI_TEAM_PROP = "Engine.PlayerReplicationInfo:Team"
RIGID_BODY_PROP = "TAGame.RBActor_TA:ReplicatedRBState"
BOOST_VEHICLE_PROP = "TAGame.CarComponent_TA:Vehicle"
BOOST_AMOUNT_PROP = "TAGame.CarComponent_Boost_TA:ReplicatedBoost"
BOOST_AMOUNT_BYTE_PROP = "TAGame.CarComponent_Boost_TA:ReplicatedBoostAmount"

CAR_CLASS = "Archetypes.Car.Car_Default"
BALL_CLASS_PREFIX = "Archetypes.Ball."
TEAM_CLASS_PREFIX = "Archetypes.Teams.Team"


@dataclass
class ActorRegistry:
    """Tracks live actor links/state across a replay's network frames."""

    objects: list[str]

    time: float = 0.0
    classes: dict[int, str] = field(default_factory=dict)
    car_to_pri: dict[int, int] = field(default_factory=dict)
    boost_component_to_car: dict[int, int] = field(default_factory=dict)
    pri_name: dict[int, str] = field(default_factory=dict)
    pri_team_actor: dict[int, int] = field(default_factory=dict)
    rigid_body: dict[int, dict] = field(default_factory=dict)
    boost_by_pri: dict[int, int] = field(default_factory=dict)

    def apply_frame(self, frame: dict) -> None:
        self.time = frame["time"]

        for actor in frame["new_actors"]:
            self.classes[actor["actor_id"]] = self.objects[actor["object_id"]]

        for update in frame["updated_actors"]:
            actor_id = update["actor_id"]
            prop = self.objects[update["object_id"]]
            attribute = update["attribute"]

            if prop == PAWN_PRI_PROP:
                if attribute["ActiveActor"]["active"]:
                    self.car_to_pri[actor_id] = attribute["ActiveActor"]["actor"]
            elif prop == PRI_NAME_PROP:
                self.pri_name[actor_id] = attribute["String"]
            elif prop == PRI_TEAM_PROP:
                if attribute["ActiveActor"]["active"]:
                    self.pri_team_actor[actor_id] = attribute["ActiveActor"]["actor"]
            elif prop == RIGID_BODY_PROP:
                self.rigid_body[actor_id] = attribute["RigidBody"]
            elif prop == BOOST_VEHICLE_PROP:
                if attribute["ActiveActor"]["active"]:
                    self.boost_component_to_car[actor_id] = attribute["ActiveActor"]["actor"]
            elif prop in (BOOST_AMOUNT_PROP, BOOST_AMOUNT_BYTE_PROP):
                car_actor_id = self.boost_component_to_car.get(actor_id)
                pri_actor_id = self.car_to_pri.get(car_actor_id) if car_actor_id is not None else None
                if pri_actor_id is not None:
                    boost_amount = (
                        attribute["ReplicatedBoost"]["boost_amount"]
                        if prop == BOOST_AMOUNT_PROP
                        else attribute["Byte"]
                    )
                    self.boost_by_pri[pri_actor_id] = boost_amount

        for actor_id in frame["deleted_actors"]:
            self.classes.pop(actor_id, None)
            self.car_to_pri.pop(actor_id, None)
            self.boost_component_to_car.pop(actor_id, None)
            self.pri_name.pop(actor_id, None)
            self.pri_team_actor.pop(actor_id, None)
            self.rigid_body.pop(actor_id, None)
            # boost_by_pri is intentionally NOT cleared here - see module
            # docstring on the boost-component channel-recycle behavior.

    def _team_number(self, pri_actor_id: int) -> Optional[int]:
        team_actor_id = self.pri_team_actor.get(pri_actor_id)
        if team_actor_id is None:
            return None
        team_class = self.classes.get(team_actor_id, "")
        if not team_class.startswith(TEAM_CLASS_PREFIX):
            return None
        return int(team_class[len(TEAM_CLASS_PREFIX) :])

    def ball_actor_id(self) -> Optional[int]:
        for actor_id, cls in self.classes.items():
            if cls.startswith(BALL_CLASS_PREFIX):
                return actor_id
        return None

    def snapshot(self) -> dict:
        """Current known state for every tracked player and the ball."""
        players = []
        for car_actor_id, pri_actor_id in self.car_to_pri.items():
            if self.classes.get(car_actor_id) != CAR_CLASS:
                continue
            players.append(
                {
                    "player_name": self.pri_name.get(pri_actor_id),
                    "team": self._team_number(pri_actor_id),
                    "car_actor_id": car_actor_id,
                    "rigid_body": self.rigid_body.get(car_actor_id),
                    "boost_amount": self.boost_by_pri.get(pri_actor_id),
                }
            )

        ball_actor_id = self.ball_actor_id()
        return {
            "time": self.time,
            "players": players,
            "ball": self.rigid_body.get(ball_actor_id) if ball_actor_id is not None else None,
        }


def iter_snapshots(replay: dict):
    """Yield a resolved (name/team/position/velocity/boost) snapshot per frame."""
    registry = ActorRegistry(objects=replay["objects"])
    for frame in replay["network_frames"]["frames"]:
        registry.apply_frame(frame)
        yield registry.snapshot()
