"""Wrapper around the rrrocket CLI for converting .replay files to JSON."""

import json
import subprocess
from pathlib import Path

RRROCKET_PATH = Path(__file__).resolve().parent.parent / "tools" / "rrrocket.exe"


class ReplayParseError(RuntimeError):
    """Raised when rrrocket fails to parse a replay file."""

""" replay_path: Path to the .replay file
    network_parse: Whether to parse the network data in the replay (default: True)
"""
def parse_replay(replay_path: Path, network_parse: bool = True) -> dict:
    replay_path = Path(replay_path)
    if not replay_path.is_file():
        raise FileNotFoundError(replay_path)
    if not RRROCKET_PATH.is_file():
        raise FileNotFoundError(f"rrrocket binary not found at {RRROCKET_PATH}")

    args = [str(RRROCKET_PATH)]
    if network_parse:
        args.append("--network-parse")
    args.append(str(replay_path))

    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise ReplayParseError(
            f"rrrocket failed on {replay_path} (exit {result.returncode}): {result.stderr.strip()}"
        )
    return json.loads(result.stdout)
