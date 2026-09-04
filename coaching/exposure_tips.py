"""Turns detectors.exposure's per-frame fuzzy scores into human-readable tips.

A raw exposure score is per-frame and per-player; on its own it's not a tip,
it's noise — a player's score crosses the threshold and drops back below it
many times a second as the ball and players move. This module groups
consecutive above-threshold frames into a single "incident" (discarding brief
one-off blips) and turns each surviving incident into one sentence.
"""

from collections import defaultdict
from dataclasses import dataclass

from detectors.exposure import exposure_score
from features.frame_features import frame_features

# A score below this isn't worth mentioning at all.
EXPOSURE_THRESHOLD = 50.0
# Frames of sustained exposure required before it's a real incident rather
# than momentary flicker as the fuzzy score crosses the threshold. ~1 second
# at the ~30fps a replay's network_frames run at.
MIN_INCIDENT_FRAMES = 30


@dataclass
class ExposurePoint:
    time: float
    score: float
    distance_to_own_goal: float
    ball_threat: float


@dataclass
class ExposureIncident:
    start_time: float
    end_time: float
    peak_score: float
    peak_distance_to_own_goal: float
    peak_ball_threat: float
    frame_count: int


def build_exposure_timeline(snapshots: list[dict]) -> dict[str, list[ExposurePoint]]:
    """One ExposurePoint per player per frame where exposure could be scored."""
    timelines: dict[str, list[ExposurePoint]] = defaultdict(list)
    for snapshot in snapshots:
        ff = frame_features(snapshot)
        for player in ff["players"]:
            if (
                player["distance_to_own_goal"] is None
                or player["ball_threat_to_own_goal"] is None
                or player["has_teammate_covering"] is None
            ):
                continue
            score = exposure_score(
                player["distance_to_own_goal"],
                player["ball_threat_to_own_goal"],
                player["has_teammate_covering"],
            )
            timelines[player["player_name"]].append(
                ExposurePoint(
                    time=ff["time"],
                    score=score,
                    distance_to_own_goal=player["distance_to_own_goal"],
                    ball_threat=player["ball_threat_to_own_goal"],
                )
            )
    return timelines


def find_incidents(
    points: list[ExposurePoint],
    threshold: float = EXPOSURE_THRESHOLD,
    min_frames: int = MIN_INCIDENT_FRAMES,
) -> list[ExposureIncident]:
    """Group consecutive points scoring >= threshold into incidents, dropping
    any run shorter than min_frames."""
    incidents = []
    run: list[ExposurePoint] = []
    for point in points:
        if point.score >= threshold:
            run.append(point)
        else:
            if len(run) >= min_frames:
                incidents.append(_close_run(run))
            run = []
    if len(run) >= min_frames:
        incidents.append(_close_run(run))
    return incidents


def _close_run(run: list[ExposurePoint]) -> ExposureIncident:
    peak = max(run, key=lambda p: p.score)
    return ExposureIncident(
        start_time=run[0].time,
        end_time=run[-1].time,
        peak_score=peak.score,
        peak_distance_to_own_goal=peak.distance_to_own_goal,
        peak_ball_threat=peak.ball_threat,
        frame_count=len(run),
    )


def _format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def format_tip(incident: ExposureIncident) -> str:
    duration = incident.end_time - incident.start_time
    severity = "badly" if incident.peak_score >= 75 else "briefly" if duration < 1.5 else "repeatedly"
    return (
        f"At {_format_time(incident.start_time)} you were {severity} out of position for "
        f"{duration:.1f}s — {incident.peak_distance_to_own_goal:.0f}uu from your own goal while "
        f"the ball threatened it ({incident.peak_ball_threat:.0%} threat) with no teammate covering."
    )


def generate_tips(
    snapshots: list[dict],
    threshold: float = EXPOSURE_THRESHOLD,
    min_frames: int = MIN_INCIDENT_FRAMES,
) -> dict[str, list[str]]:
    """player_name -> list of tip sentences, for every player with at least
    one qualifying exposure incident across the replay."""
    timelines = build_exposure_timeline(snapshots)
    tips = {}
    for player_name, points in timelines.items():
        incidents = find_incidents(points, threshold, min_frames)
        if incidents:
            tips[player_name] = [format_tip(incident) for incident in incidents]
    return tips
