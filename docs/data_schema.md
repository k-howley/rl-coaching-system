# Parsed Replay JSON Schema

Source: `rrrocket` v0.11.5, run with `--network-parse` (see `parser/rrrocket.py`).
Output written by `parser/pipeline.py` to `data/parsed/<replay-name>.json`.

Sanity numbers from 3 real sample replays: ~1.4-1.7MB `.replay` in, ~17-21MB JSON
out, ~10,900 frames for a ~6 minute match (~30 frames/sec).

## Top-level keys

| Key | Purpose |
|---|---|
| `header_size`, `header_crc` | Raw header framing. Not needed for analysis. |
| `major_version`, `minor_version`, `net_version` | Engine build the replay was recorded on. Determines the network property layout rrrocket had to decode against. |
| `game_type` | e.g. `TAGame.GameInfo_Soccar_TA` |
| `properties` | Match header/summary (see below). |
| `content_size`, `content_crc` | Raw content framing. Not needed for analysis. |
| `network_frames.frames` | List of per-tick game state deltas. The actual replicated gameplay data (see below). |
| `levels` | Map file(s) loaded. |
| `keyframes`, `tick_marks` | Seek markers for the in-game replay player. Not needed for analysis. |
| `debug_info` | rrrocket-internal diagnostics. |
| `packages`, `objects`, `names`, `class_indices`, `net_cache` | Lookup tables used to decode `object_id`/`name_id` references inside `network_frames` (see "Resolving actor identity" below). |

## `properties` (match header)

Key fields observed:

- `TeamSize`, `UnfairTeamSize`
- `Team0Score`, `Team1Score`
- `Goals`: list of `{frame, PlayerName, PlayerTeam}`
- `HighLights`: list of `{frame, CarName, BallName, GoalActorName}`
- `PlayerStats`: list of per-player summaries:
  ```json
  {
    "Name": "the grand",
    "Platform": { "kind": "OnlinePlatform", "value": "OnlinePlatform_Steam" },
    "OnlineID": "76561199008500031",
    "Team": 0,
    "Score": 426,
    "Goals": 1,
    "Assists": 1,
    "Saves": 2,
    "Shots": 2,
    "bBot": false
  }
  ```
- `MapName`, `MatchType`, `Date`, `NumFrames`, `GameVersion`, `BuildID`,
  `ReplayVersion`, `ReplayLastSaveVersion`, `ReplayName`: replay/engine metadata.

Known quirk: some `PlayerName`/`ReplayName` values with accented characters come
through mojibake (e.g. `"FibÃ©rr"` instead of `"Fibérr"`), which looks like a
UTF-8 byte sequence getting re-decoded as Latin-1 somewhere upstream. Worth
re-checking before using player names as join keys or displaying them.

## `network_frames.frames[i]`

One entry per network tick:

- `time`: seconds elapsed since replay start
- `delta`: seconds since previous frame (~0.033 at 30fps)
- `new_actors`: actors spawned this frame:
  ```json
  {
    "actor_id": 0,
    "name_id": 0,
    "object_id": 68,
    "initial_trajectory": {
      "location": { "x": 0, "y": 0, "z": 93 },
      "rotation": { "yaw": null, "pitch": null, "roll": null }
    }
  }
  ```
- `deleted_actors`: list of `actor_id` values removed this frame
- `updated_actors`: property updates for actors that already exist:
  ```json
  {
    "actor_id": 0,
    "stream_id": 42,
    "object_id": 46,
    "attribute": { "RigidBody": { "...": "..." } }
  }
  ```

### Resolving actor identity

`new_actors[i].object_id` indexes into the top-level `objects` array to get the
actor's class, e.g.:

- `objects[68]` = `"Archetypes.Ball.Ball_Default"`: this actor is the ball
- `objects[212]` = `"TAGame.Default__PRI_TA"`: this actor is a player's
  PlayerReplicationInfo (name/team/score bookkeeping, not the car itself)

`name_id` indexes into `names` for a per-instance debug label (e.g.
`"Ball_TA_354"`), not a stable identifier.

**Actor IDs are reused during a match.** When a car is destroyed and respawned,
its old `actor_id` can be handed to something new. An `actor_id` alone does not
identify "the same player" across the whole replay. You have to walk
`new_actors`/`deleted_actors` frame-by-frame to know what a given `actor_id`
currently refers to at time `T`.

`parser/actor_tracker.py` solves this: `iter_snapshots(replay)` walks the frame
stream once and yields one resolved snapshot per frame,
`{time, players: [{player_name, team, car_actor_id, rigid_body, boost_amount}], ball: <rigid_body>}`,
by following these links:

- `Engine.Pawn:PlayerReplicationInfo` (car actor to PRI actor)
- `Engine.PlayerReplicationInfo:PlayerName` / `:Team` (PRI actor to name / team actor)
- `TAGame.CarComponent_TA:Vehicle` (boost component actor to owning car actor)
- `TAGame.RBActor_TA:ReplicatedRBState` (car/ball actor to position/velocity, direct)

Verified against all 3 real sample replays: every player in the match header's
`PlayerStats` resolves correctly across their full time in the match, including
through car demolitions/respawns (each respawn gets a new `actor_id`, covered
by `tests/test_actor_tracker.py::test_survives_car_respawn_with_new_actor_id`).

### `ActiveActor` links can go temporarily inactive: don't overwrite with -1

`ActiveActor` values aren't always a real link: Unreal sends
`{"active": false, "actor": -1}` as the idiom for "this reference is
temporarily unset," observed on `Engine.Pawn:PlayerReplicationInfo` during a
car respawn transition (9 of 254 updates in one sample replay). The original
code stored this blindly, setting `car_to_pri[car_id] = -1` and breaking name
resolution (`pri_name.get(-1)` returns `None`) until the next real link update
arrived. Real, product-visible impact: a coaching-tip generation pass
(`coaching/exposure_tips.py`) attributed several legitimate high-exposure
incidents, one 21.5 seconds long, to a "None" player instead of the real
one, across all 3 sample replays, before this was fixed. Fix: `active: false`
updates on any `ActiveActor` link (car to PRI, PRI to team, boost to car) are now
ignored, keeping the last known good mapping. Covered by
`tests/test_actor_tracker.py::test_pawn_pri_link_ignores_transient_inactive_update`;
confirmed against real data this dropped `player_name is None` from ~2% to
0.00% across all 3 sample replays.

### Boost component channel recycling (real behavior, not a bug)

Unlike the car/PRI actors, the boost component actor gets **periodically
deleted and replaced with a brand-new actor_id mid-match with no gameplay
event involved.** A batch of unrelated components (boost, and presumably
other low-priority ones) all reset together every ~1500-3000 frames, most
likely a replication-channel recycle in the recording. Confirmed against real
replay data: in one sample, boost actor 18 (car 23) received 1931 boost
updates, then was deleted at frame 1736/10935 and never replaced with a new
linked component for the rest of the match. A naive "clear on delete" design
loses ~85% of that player's boost data for nothing.

Fix: boost is anchored to the player's **PRI actor_id** (proven stable for the
whole match) rather than the transient boost-component actor_id, and is never
cleared when the component is deleted, only overwritten by a newer value.
See `tests/test_actor_tracker.py::test_boost_survives_component_channel_recycle_with_no_new_value`.
This dropped the None-rate for `boost_percent` across all 3 sample replays
from as high as 100% down to 0.3-2.5% (in line with the normal ~2-3%
None-rate for `speed`, from bodies being `sleeping` at kickoff/pauses).

### Two boost property variants exist in the wild

Some real replays never send `TAGame.CarComponent_Boost_TA:ReplicatedBoost`
(the composite struct) at all. They only send
`TAGame.CarComponent_Boost_TA:ReplicatedBoostAmount`, a plain
`{"Byte": <0-255>}`. Observed in one of the 3 sample replays, same
`net_version` as the other two that do use `ReplicatedBoost`. Both are handled
in `parser/actor_tracker.py`.

### `updated_actors[i].attribute` shapes seen so far

| Attribute | Shape | Notes |
|---|---|---|
| `RigidBody` | `{sleeping, location:{x,y,z}, rotation:{x,y,z,w}, linear_velocity:{x,y,z}\|null, angular_velocity:{x,y,z}\|null}` | Position/orientation (quaternion)/velocity for cars and the ball. **Primary source for Week 3 distance/velocity/rotation features.** `linear_velocity`/`angular_velocity` are `null` while the body is `sleeping`. |
| `ReplicatedBoost` | `{grant_count, boost_amount, unused1, unused2}` | `boost_amount` in range 0-255. One of two boost-amount property variants, see above. |
| `ReplicatedBoostAmount` | `{Byte: 0-255}` | The other boost-amount property variant, see above. |
| `ActiveActor` | `{active: bool, actor: <actor_id>}` | Links one actor to another (e.g. camera to car). Needed for actor-identity reconstruction above. |
| `PickupNew` | `{instigator: <actor_id>, picked_up: 0\|1}` | Boost pad pickup events. No pad location/size in this attribute; would need to be cross-referenced against a known boost pad map layout. |
| `Int`, `Int64`, `Float`, `Byte`, `Boolean`, `String`, `Enum` | primitive | Misc replicated values (score, loadout indices, etc.) attached to PRI/car actors. |
| `TeamPaint`, `TeamLoadout`, `LoadoutsOnline`, `CamSettings`, `UniqueId`, `Reservation`, `PartyLeader`, `Location` | various | Cosmetic/session bookkeeping, not gameplay-relevant. |

## Open work / not yet built

- Boost pad reference table (map-specific pad locations/sizes) to interpret
  `PickupNew` events.
- Validation of the `PlayerName`/`ReplayName` encoding issue above.
- `features/` now computes speed, boost%, uprightness, distance-to-ball,
  distance-to-own-goal, ball-threat-to-goal, and has-teammate-covering per
  player per frame (see `features/frame_features.py`), but none of this is
  wired into `parser/pipeline.py`'s output yet, and no fuzzy detection
  (`detectors/`, `scikit-fuzzy`) or tip generation (`coaching/`) exists yet.
