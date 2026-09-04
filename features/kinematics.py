"""Per-entity physical features derived from a single rigid_body dict
(see docs/data_schema.md for the rigid_body shape)."""

from typing import Optional

from features.vectors import magnitude


def speed(rigid_body: Optional[dict]) -> Optional[float]:
    """Linear speed in unreal units/sec. Rocket League's supersonic cap is 2300
    uu/s, useful as a sanity bound. None if unknown (body is sleeping)."""
    if rigid_body is None or rigid_body["linear_velocity"] is None:
        return None
    return magnitude(rigid_body["linear_velocity"])


def boost_percent(boost_amount: Optional[int]) -> Optional[float]:
    """rrrocket reports boost as a raw 0-255 byte; convert to the 0-100 value
    shown in-game."""
    if boost_amount is None:
        return None
    return (boost_amount / 255.0) * 100.0


def uprightness(rigid_body: Optional[dict]) -> Optional[float]:
    """How right-side-up the car is, from its rotation quaternion (x, y, z, w).

    This is the Z-component of the car's local up-vector after rotation:
    1 - 2*(x^2 + y^2), derived from the standard quaternion-to-rotation-matrix
    formula for a unit quaternion. +1.0 = flat on wheels, -1.0 = flat on roof,
    0.0 = balanced on a side/wall.
    """
    if rigid_body is None or rigid_body["rotation"] is None:
        return None
    q = rigid_body["rotation"]
    if q["x"] is None:
        return None
    return 1.0 - 2.0 * (q["x"] ** 2 + q["y"] ** 2)


def is_upside_down(rigid_body: Optional[dict], threshold: float = 0.0) -> Optional[bool]:
    up = uprightness(rigid_body)
    if up is None:
        return None
    return up < threshold
