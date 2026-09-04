"""Replay-to-JSON conversion: a single-replay entry point for the eventual
coaching GUI, plus a batch mode used for dev/testing against many samples."""

import argparse
import json
import logging
from pathlib import Path

from parser.actor_tracker import iter_snapshots
from parser.rrrocket import ReplayParseError, parse_replay

logger = logging.getLogger(__name__)

DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_PARSED_DIR = Path("data/parsed")


def process_replay(replay_path: Path) -> tuple[dict, list[dict]]:
    """Parse one replay and resolve it into per-frame player/ball snapshots.

    This is the entry point a future caller (e.g. a GUI where a user picks a
    single replay) uses to get everything needed for feature extraction /
    fuzzy detection on that one replay. Returns (raw_replay_json, snapshots)
    without writing anything to disk.
    """
    data = parse_replay(Path(replay_path))
    snapshots = list(iter_snapshots(data))
    return data, snapshots


def run_pipeline(
    raw_dir: Path = DEFAULT_RAW_DIR, parsed_dir: Path = DEFAULT_PARSED_DIR
) -> list[Path]:
    """Parse every .replay file in raw_dir and write JSON output to parsed_dir.

    Dev/testing utility for validating the parser against many samples at
    once (e.g. a Kaggle batch). The coaching product's actual usage is
    single-replay, via process_replay() above.
    """
    raw_dir = Path(raw_dir)
    parsed_dir = Path(parsed_dir)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for replay_path in sorted(raw_dir.glob("*.replay")):
        try:
            data, snapshots = process_replay(replay_path)
        except ReplayParseError as exc:
            logger.error("Skipping %s: %s", replay_path.name, exc)
            continue

        output_path = parsed_dir / f"{replay_path.stem}.json"
        output_path.write_text(json.dumps(data), encoding="utf-8")
        written.append(output_path)

        snapshots_path = parsed_dir / f"{replay_path.stem}.snapshots.json"
        snapshots_path.write_text(json.dumps(snapshots), encoding="utf-8")
        written.append(snapshots_path)

        logger.info("Parsed %s -> %s, %s", replay_path.name, output_path.name, snapshots_path.name)

    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    arg_parser = argparse.ArgumentParser(description="Convert .replay files into parsed JSON.")
    arg_parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    arg_parser.add_argument("--parsed-dir", type=Path, default=DEFAULT_PARSED_DIR)
    args = arg_parser.parse_args()

    written = run_pipeline(args.raw_dir, args.parsed_dir)
    print(f"Parsed {len(written)} replay(s) into {args.parsed_dir}")


if __name__ == "__main__":
    main()
