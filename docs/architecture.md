# Architecture / Call Graph

What each file does, what each function does, and what actually calls what.
Keep this updated as files/functions change: it's meant to be the map you
check before touching unfamiliar code, not a one-time snapshot.

For the shape of the JSON these functions produce/consume, see
[data_schema.md](data_schema.md).

## The two entry points

1. **Single replay (the real product)**: `parser.pipeline.process_replay(path)`.
   This is what a future GUI calls: user picks one `.replay`, gets back
   everything needed to run features/fuzzy detection on it. Nothing is
   written to disk.
2. **Batch (dev/testing only)**: `python -m parser.pipeline`, or
   `parser.pipeline.run_pipeline(raw_dir, parsed_dir)`. Loops
   `process_replay()` over every `.replay` in a directory and writes the
   results to disk. Used for validating the parser against many samples
   (e.g. a Kaggle batch), not part of the coaching workflow itself.

## Files and functions

### `parser/rrrocket.py`: talks to the external rrrocket binary

- `RRROCKET_PATH`: path to `tools/rrrocket.exe` (downloaded from the
  [rrrocket](https://github.com/nickbabcock/rrrocket) GitHub releases; not a
  Python package, not on PATH).
- `ReplayParseError(RuntimeError)`: raised when rrrocket exits non-zero
  (corrupt file, unsupported replay version, etc).
- `parse_replay(replay_path, network_parse=True) -> dict`: validates the
  replay file and the rrrocket binary both exist, shells out to
  `rrrocket.exe [--network-parse] <replay_path>`, parses its stdout JSON.
  Returns rrrocket's raw output: header/`properties` + `network_frames`.
  **Called by:** `parser.pipeline.process_replay`.

### `parser/actor_tracker.py`: resolves raw actor-id churn into stable state

rrrocket's `network_frames` only exposes short-lived `actor_id`s that get
reused; this file turns that into "what is player X doing right now."

- Constants: property-name strings used to recognize specific fields inside
  an `updated_actors` entry (`PAWN_PRI_PROP`, `PRI_NAME_PROP`, `PRI_TEAM_PROP`,
  `RIGID_BODY_PROP`, `BOOST_VEHICLE_PROP`, `BOOST_AMOUNT_PROP`), and
  class-name strings used to recognize actor types (`CAR_CLASS`,
  `BALL_CLASS_PREFIX`, `TEAM_CLASS_PREFIX`). See data_schema.md for how these
  were identified.
- `ActorRegistry` (dataclass): the live state, keyed by `actor_id`:
  - `apply_frame(frame)`: ingests one `network_frames` frame. Registers new
    actors' classes, applies property updates (car->PRI link, PRI name/team,
    rigid body, boost-component->car link, boost amount), then removes
    anything in `deleted_actors` from every tracked dict.
  - `_team_number(pri_actor_id)`: resolves a player's team (0/1) by looking
    up the Team actor their PRI links to and reading the digit off its class
    name (`Archetypes.Teams.Team0`/`Team1`).
  - `ball_actor_id()`: finds the currently-live actor whose class starts
    with `Archetypes.Ball.`.
  - `snapshot()`: builds the current resolved view. One dict per tracked
    player (`player_name`, `team`, `car_actor_id`, `rigid_body`,
    `boost_amount`) plus the ball's `rigid_body`.
- `iter_snapshots(replay)`: generator. Builds one `ActorRegistry` for the
  whole replay, calls `apply_frame()` then yields `snapshot()` for every
  frame in `replay["network_frames"]["frames"]`.
  **Called by:** `parser.pipeline.process_replay`.

### `parser/pipeline.py`: the entry points described above

- `process_replay(replay_path) -> (raw_json, snapshots)`: calls
  `parse_replay()` then `iter_snapshots()`. No disk I/O.
- `run_pipeline(raw_dir, parsed_dir) -> list[Path]`: for each `*.replay` in
  `raw_dir`, calls `process_replay()`, catches `ReplayParseError` and skips
  (logs + continues) on failure, writes `<stem>.json` (raw) and
  `<stem>.snapshots.json` (resolved) into `parsed_dir`. Returns every path
  written.
- `main()`: argparse CLI (`--raw-dir`, `--parsed-dir`) wrapping
  `run_pipeline()`. Invoked via `python -m parser.pipeline`.

### `conftest.py` (repo root)

Pytest auto-loads this before collecting tests. Puts the repo root on
`sys.path` so `from parser import ...` resolves inside `tests/` no matter
what directory pytest is invoked from.

### `tests/`

- `test_rrrocket.py`: `parse_replay`, covering missing replay file, missing
  rrrocket binary, successful parse, non-zero-exit failure. `subprocess.run`
  is mocked; no real binary invoked.
- `test_actor_tracker.py`: `ActorRegistry`/`iter_snapshots` against small
  synthetic frames. Resolves name/team/rigid-body/boost correctly, and
  (the important one) survives a car being deleted and respawned under a
  brand-new `actor_id` without losing the player.
- `test_pipeline.py`: `process_replay` (no disk writes) and `run_pipeline`
  (writes both output files, skips files that fail to parse).
  `parse_replay`/`iter_snapshots` are mocked; these tests check pipeline
  wiring, not parsing correctness.

### `tools/rrrocket.exe`

Not Python. The actual `.replay` binary format decoder. Everything above is
a thin layer around its output.

### `features/`: turns a snapshot into per-player numeric signals

Pure functions, one snapshot in, feature values out. Deliberately kept as
separate crisp values rather than combined into precomputed scores. Combining
them via fuzzy membership functions/rules is `detectors/`'s job, not this
layer's. **Not yet wired into `parser/pipeline.py`**: nothing calls these
automatically after parsing.

- `features/vectors.py`: `magnitude(v)`, `distance(a, b)` on plain
  `{x,y,z}` dicts. Used by everything else in this package.
- `features/kinematics.py`: per-`rigid_body` physics.
  - `speed(rigid_body)`: linear velocity magnitude (uu/s; RL's supersonic
    cap is 2300, useful as a sanity bound). `None` while sleeping.
  - `boost_percent(boost_amount)`: converts rrrocket's raw 0-255 byte to
    the in-game 0-100 display value.
  - `uprightness(rigid_body)`: car's up-vector Z component from its
    rotation quaternion; +1 flat on wheels, -1 flat on roof, 0 on a side.
  - `is_upside_down(rigid_body, threshold=0.0)`: `uprightness(...) < threshold`.
- `features/field.py`: standard Soccar field constants. `GOAL_Y = 5120.0`,
  `own_goal_location(team)` (team 0 defends -Y, team 1 defends +Y, verified
  against real goal events in `docs/data_schema.md`). Not valid for
  Hoops/Dropshot/Rumble.
- `features/positioning.py`: team-relative positioning.
  - `distance_to_own_goal(rigid_body, team)`
  - `ball_threat_to_goal(ball_rigid_body, team)`: 0 (ball far away) to 1
    (ball on this team's goal line)
  - `has_teammate_covering(player, players)`: is some other teammate
    currently closer to the own goal than this player
- `features/frame_features.py`: the aggregator. `player_features(player,
  players, ball)` builds one feature dict per player; `frame_features(snapshot)`
  runs that for every player in a snapshot and adds `ball_speed`. This is the
  function any future caller (detectors, or ad-hoc analysis) should call per
  snapshot; everything above it is a building block.

### `detectors/`: combines crisp features into fuzzy scores

- `detectors/exposure.py`: `exposure_score(distance_to_own_goal, ball_threat,
  has_teammate_covering) -> float` (0-100). A Mamdani fuzzy inference system:
  3 terms each for distance (close/medium/far) and ball_threat
  (low/medium/high), 2 terms for covering (no/yes), a complete 3x3x2 rule
  table (`_DECISION_TABLE`), centroid defuzzification. Built with skfuzzy's
  low-level `interp_membership`/`defuzz` functions directly, **not**
  `skfuzzy.control`'s `Antecedent`/`Rule`/`ControlSystemSimulation` classes.
  See the module docstring and the perf note below for why. Verified against
  a real match: ~0.09ms/call, 6.1s for a full replay's ~66k player-frames.

**Performance trap to remember for any future detector using scikit-fuzzy:**
`skfuzzy.control.ControlSystemSimulation` costs ~10ms per `.compute()` call
regardless of its own input-caching (measured directly against real replay
data, not synthetic repeated inputs). Its cache stores every seen input in a
plain Python list and checks membership with a linear `in` scan
(`controlsystem.py:352`); real gameplay data is essentially always unique
values, so it's a 100% cache-miss workload paying for a cache that never
helps, and the scan cost grows as the list does. At tens of thousands of
calls per replay this is minutes, not seconds. Use the low-level functions
(`fuzz.trimf`, `fuzz.interp_membership`, `fuzz.defuzz`) directly instead, as
`exposure.py` does: same Mamdani math, ~200x faster, no growing cache.

### `coaching/`: turns fuzzy scores into tip sentences

- `coaching/exposure_tips.py`: the first (only) tip generator, built on
  `detectors.exposure`:
  - `build_exposure_timeline(snapshots) -> dict[player_name, list[ExposurePoint]]`:
    runs `frame_features` + `exposure_score` for every player in every
    snapshot, skipping players missing any required feature that frame.
  - `find_incidents(points, threshold=50.0, min_frames=30)`: a raw per-frame
    score is noise on its own (crosses the threshold many times a second as
    play moves); this groups consecutive above-threshold points into one
    incident and drops runs shorter than `min_frames` (~1s) as flicker.
  - `format_tip(incident) -> str`: one human-readable sentence per incident
    (timestamp, duration, peak distance/threat).
  - `generate_tips(snapshots) -> dict[player_name, list[str]]`: the actual
    entry point. Ties the three functions above together for a whole replay.
    Verified against all 3 real sample replays; ~6s per replay (dominated by
    `exposure_score`, not the grouping logic).

## Call graph: single-replay path (the one that matters)

```
caller (future GUI)
  -> parser.pipeline.process_replay(path)
       -> parser.rrrocket.parse_replay(path)
            -> subprocess: tools/rrrocket.exe --network-parse <path>
            <- raw replay JSON (properties + network_frames)
       -> parser.actor_tracker.iter_snapshots(raw_json)
            -> ActorRegistry.apply_frame(frame)   ┐ per frame, in order
            -> ActorRegistry.snapshot()           ┘
            <- list[{time, players: [...], ball}]
  <- (raw_json, snapshots)
```

## Call graph: batch/dev path

```
$ python -m parser.pipeline [--raw-dir DIR] [--parsed-dir DIR]
  -> main()
       -> run_pipeline(raw_dir, parsed_dir)
            for each *.replay in raw_dir:
              -> process_replay(replay_path)   (same as above)
              -> writes <stem>.json + <stem>.snapshots.json to parsed_dir
```

## Call graph: features -> detector -> tips

```
data, snapshots = process_replay(path)          # parser.pipeline
tips = coaching.exposure_tips.generate_tips(snapshots)
  for snapshot in snapshots:
      ff = features.frame_features.frame_features(snapshot)
      for player in ff["players"]:
          detectors.exposure.exposure_score(
              player["distance_to_own_goal"],
              player["ball_threat_to_own_goal"],
              player["has_teammate_covering"],
          ) -> 0-100 fuzzy exposure score
          -> collected into an ExposurePoint per player per frame
  find_incidents(points)   # group sustained above-threshold runs per player
  format_tip(incident)     # -> one sentence per incident
<- {player_name: [tip sentence, ...]}
```

`generate_tips()` is the actual current top-level entry point for "give me
coaching feedback on this replay," verified end-to-end against all 3 real
sample replays (~6s each, correctly attributed to real players, no more
"None" entries after the `active: false` fix in docs/data_schema.md).

## Not built yet

- Only one detector/tip generator exists (`exposure`). Boost management,
  rotation/positioning beyond exposure, etc. from the original feature list
  have crisp features in `features/` but no fuzzy detector or tip generator
  consuming them yet.
- Nothing combines multiple detectors' tips into one coherent report for a
  replay, or ranks/limits how many tips get shown.
- No GUI. `process_replay()` exists as the function a GUI will call, but no
  GUI code exists yet.
