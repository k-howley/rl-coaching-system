"""Standard Soccar field geometry.

Only valid for the standard Soccar game mode (game_type
TAGame.GameInfo_Soccar_TA) — Hoops/Dropshot/Rumble use different field
dimensions and are not handled here.
"""

GOAL_Y = 5120.0
FIELD_LENGTH = 2 * GOAL_Y


def own_goal_location(team: int) -> dict:
    """Team 0 (Blue) defends -Y, Team 1 (Orange) defends +Y.

    Verified against real replay data (see docs/data_schema.md): at each
    scored-goal event, the ball's Y position is negative when the scoring
    PlayerTeam is 1 and positive when it's 0 — i.e. a team scores into the
    opposing team's (this function's) goal location.
    """
    return {"x": 0.0, "y": -GOAL_Y if team == 0 else GOAL_Y, "z": 0.0}
