import json
import subprocess

import pytest

from parser import rrrocket


def test_parse_replay_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        rrrocket.parse_replay(tmp_path / "missing.replay")


def test_parse_replay_missing_binary(tmp_path, monkeypatch):
    replay_path = tmp_path / "sample.replay"
    replay_path.write_bytes(b"fake replay bytes")
    monkeypatch.setattr(rrrocket, "RRROCKET_PATH", tmp_path / "does-not-exist.exe")

    with pytest.raises(FileNotFoundError):
        rrrocket.parse_replay(replay_path)


def test_parse_replay_success(tmp_path, monkeypatch):
    replay_path = tmp_path / "sample.replay"
    replay_path.write_bytes(b"fake replay bytes")
    fake_binary = tmp_path / "rrrocket.exe"
    fake_binary.write_bytes(b"")
    monkeypatch.setattr(rrrocket, "RRROCKET_PATH", fake_binary)

    expected = {"header": {"engine_version": 868}}

    def fake_run(args, capture_output, text):
        assert str(replay_path) in args
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(expected), stderr="")

    monkeypatch.setattr(rrrocket.subprocess, "run", fake_run)

    result = rrrocket.parse_replay(replay_path)
    assert result == expected


def test_parse_replay_failure(tmp_path, monkeypatch):
    replay_path = tmp_path / "sample.replay"
    replay_path.write_bytes(b"fake replay bytes")
    fake_binary = tmp_path / "rrrocket.exe"
    fake_binary.write_bytes(b"")
    monkeypatch.setattr(rrrocket, "RRROCKET_PATH", fake_binary)

    def fake_run(args, capture_output, text):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="corrupt replay")

    monkeypatch.setattr(rrrocket.subprocess, "run", fake_run)

    with pytest.raises(rrrocket.ReplayParseError, match="corrupt replay"):
        rrrocket.parse_replay(replay_path)
