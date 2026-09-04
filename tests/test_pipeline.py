import json

from parser import pipeline
from parser.rrrocket import ReplayParseError


def test_process_replay_returns_data_and_snapshots_without_writing(tmp_path, monkeypatch):
    replay_path = tmp_path / "match.replay"
    replay_path.write_bytes(b"fake")

    def fake_parse_replay(path, network_parse=True):
        return {"file": path.name}

    def fake_iter_snapshots(data):
        yield {"time": 0.0, "players": [], "ball": None}
        yield {"time": 0.033, "players": [], "ball": None}

    monkeypatch.setattr(pipeline, "parse_replay", fake_parse_replay)
    monkeypatch.setattr(pipeline, "iter_snapshots", fake_iter_snapshots)

    data, snapshots = pipeline.process_replay(replay_path)

    assert data == {"file": "match.replay"}
    assert snapshots == [
        {"time": 0.0, "players": [], "ball": None},
        {"time": 0.033, "players": [], "ball": None},
    ]
    # process_replay is the no-disk-writes entry point
    assert list(tmp_path.iterdir()) == [replay_path]


def test_run_pipeline_writes_json(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    parsed_dir = tmp_path / "parsed"
    raw_dir.mkdir()
    (raw_dir / "match1.replay").write_bytes(b"fake")
    (raw_dir / "match2.replay").write_bytes(b"fake")

    def fake_parse_replay(path, network_parse=True):
        return {"file": path.name}

    def fake_iter_snapshots(data):
        yield {"time": 0.0, "players": [], "ball": None}

    monkeypatch.setattr(pipeline, "parse_replay", fake_parse_replay)
    monkeypatch.setattr(pipeline, "iter_snapshots", fake_iter_snapshots)

    written = pipeline.run_pipeline(raw_dir, parsed_dir)

    assert len(written) == 4
    raw_outputs = [p for p in written if not p.name.endswith(".snapshots.json")]
    snapshot_outputs = [p for p in written if p.name.endswith(".snapshots.json")]
    assert len(raw_outputs) == 2
    assert len(snapshot_outputs) == 2

    for output_path in raw_outputs:
        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["file"].endswith(".replay")

    for output_path in snapshot_outputs:
        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data == [{"time": 0.0, "players": [], "ball": None}]


def test_run_pipeline_skips_failed_parse(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    parsed_dir = tmp_path / "parsed"
    raw_dir.mkdir()
    (raw_dir / "broken.replay").write_bytes(b"fake")

    def fake_parse_replay(path, network_parse=True):
        raise ReplayParseError("corrupt")

    monkeypatch.setattr(pipeline, "parse_replay", fake_parse_replay)

    written = pipeline.run_pipeline(raw_dir, parsed_dir)

    assert written == []
    assert list(parsed_dir.glob("*.json")) == []
