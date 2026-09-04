"""Generic 3D vector helpers shared by feature calculations.

Vectors are plain {"x", "y", "z"} dicts, matching the shape rrrocket/
actor_tracker already use for location/velocity, so no wrapper type is needed.
"""


def magnitude(v: dict) -> float:
    return (v["x"] ** 2 + v["y"] ** 2 + v["z"] ** 2) ** 0.5


def distance(a: dict, b: dict) -> float:
    return magnitude({"x": a["x"] - b["x"], "y": a["y"] - b["y"], "z": a["z"] - b["z"]})
