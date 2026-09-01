from __future__ import annotations

from pystages.cncrouter import CNCError, CNCState, describe_grbl_alarm

GRBL_ALARM_DESCRIPTIONS: dict[int, str] = {
    2: (
        "Soft limit exceeded: requested motion is outside allowed travel. "
        'Position retained. Click "Reset GRBL" then "Unlock" if needed.'
    ),
}


def describe_grbl_alarm_ui(alarm_code: int) -> str:
    return GRBL_ALARM_DESCRIPTIONS.get(alarm_code, describe_grbl_alarm(alarm_code))


def format_grbl_alarm_message(error: CNCError) -> str:
    """Format a CNCError raised on a Grbl ALARM for display in LaserStudio."""
    if error.status.state != CNCState.ALARM or error.status.substate is None:
        return str(error)
    description = describe_grbl_alarm_ui(error.status.substate)
    detail = error.args[0] if error.args else ""
    if detail:
        return f"ALARM:{error.status.substate} — {description} ({detail})"
    return f"ALARM:{error.status.substate} — {description}"
