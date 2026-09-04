# RL Coaching System

Final year project. Takes a single Rocket League `.replay` file and produces
plain-English coaching tips for the players in it, using a fuzzy logic
detector instead of a trained ML model. Analyzes one replay at a time; this
is not a batch dataset pipeline, though a batch mode exists for testing the
parser against many samples at once.

Right now there's one working detector: **exposure** (a player being caught
too far from their own goal while the ball threatens it, with no teammate
covering). More detectors (boost management, rotation) are planned but not
built yet.

## How it works

```
.replay file
  -> rrrocket.exe (external binary, --network-parse)
  -> parser/: resolve raw network frames into per-frame player/ball state
  -> features/: turn each frame into crisp numeric signals per player
       (speed, boost %, distance to own goal, ball threat, teammate covering...)
  -> detectors/: fuzzy logic (scikit-fuzzy) turns those signals into a
       0-100 "exposure score" per player per frame
  -> coaching/: groups sustained high-exposure runs into incidents and
       writes a tip sentence for each one
  -> {player_name: [tip, tip, ...]}
```

See `docs/architecture.md` for the full file-by-file breakdown and call
graph, and `docs/data_schema.md` for the shape of the parsed replay JSON and
the quirks of Rocket League's replay format that the parser works around
(actor ID reuse, transient inactive links, boost channel recycling, etc).

## Why fuzzy logic instead of a fuzzy-sounding ML model

Player exposure isn't a hard threshold. "Close to goal" and "far from goal"
are matters of degree, and the same is true of ball threat. Fuzzy membership
functions and a rule table model that directly, and stay interpretable: every
tip can be traced back to which rule fired, without needing a labeled
training set of "bad positioning" replays that doesn't exist.

## Requirements

- Python 3.14 (see `venv/pyvenv.cfg`; earlier 3.x likely works too but isn't
  tested here)
- `tools/rrrocket.exe`, a prebuilt Windows binary of
  [rrrocket](https://github.com/nickbabcock/rrrocket) (already vendored in
  this repo under `tools/`). It's not a Python package and isn't put on
  `PATH`, so `parser/rrrocket.py` calls it directly by path.
- Dependencies in `requirements.txt` (notably `scikit-fuzzy`, `numpy`,
  `scipy`, `pandas`, `pytest`; the rest is Jupyter tooling used for
  exploration in `notebooks/`)

## Setup

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Usage

Analyze a single replay (the actual product path, nothing is written to
disk):

```python
from parser.pipeline import process_replay
from coaching.exposure_tips import generate_tips

raw_json, snapshots = process_replay("data/raw/some-match.replay")
tips = generate_tips(snapshots)
# {"player name": ["At 1:32, spent 21.5s far from goal with the ball ...", ...]}
```

Batch-parse a directory of replays (dev/testing only, used to validate the
parser against many sample files, not part of the coaching workflow):

```bash
python -m parser.pipeline --raw-dir data/raw --parsed-dir data/parsed
```

## Testing

```bash
pytest
```

Tests cover the parser (mocked `rrrocket.exe`/subprocess calls), actor
tracking against synthetic frames (including car respawns and transient
link drops), feature calculations, and the exposure detector/tip generator.
All of `parser/`, `features/`, `detectors/`, and `coaching/` are also
verified end-to-end against 3 real sample replays checked into `data/raw/`.

## Project layout

```
parser/      external rrrocket call + actor-id resolution -> per-frame snapshots
features/    snapshot -> crisp per-player numeric signals (pure functions)
detectors/   crisp signals -> fuzzy 0-100 scores (scikit-fuzzy, low-level API)
coaching/    fuzzy scores -> grouped incidents -> tip sentences
tests/       pytest suite for all of the above
docs/        architecture map and replay JSON schema notes
notebooks/   exploratory analysis
data/        sample .replay files (raw/) and parsed JSON output (parsed/)
tools/       vendored rrrocket.exe
```

## A note on scikit-fuzzy performance

`detectors/exposure.py` builds its fuzzy inference system with skfuzzy's
low-level `interp_membership`/`defuzz` functions, not the higher-level
`skfuzzy.control` (`Antecedent`/`Rule`/`ControlSystemSimulation`) API.
`ControlSystemSimulation.compute()` measured at ~10ms per call against real
replay data regardless of its own input caching (its cache does a linear
`in` scan over every distinct input ever seen, and gameplay data is
essentially always unique, a 100% cache-miss workload). At tens of
thousands of calls per replay that's minutes, not seconds. The low-level
functions do the same Mamdani math in ~0.09ms per call, about 200x faster,
with no growing cache to pay for. Worth remembering before building any
future detector on top of scikit-fuzzy.

## Status / not built yet

- Only the exposure detector/tip generator exists end to end. Boost
  management and rotation/positioning features are computed in `features/`
  but have no fuzzy detector or tip generator consuming them yet.
- Nothing combines multiple detectors' tips into one ranked report per
  replay (moot for now since there's only one detector).
- No GUI. `process_replay()` is the function a future GUI is meant to call,
  but no GUI code exists yet.
