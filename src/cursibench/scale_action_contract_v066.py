"""Pre-result cell-neutral v0.6.6 GUI action extensions.

The v0.6 full action validator and all prior evidence remain untouched. This
wrapper validates new native-relevant GUI actions by projecting them onto the
old validator's exact current-frame, task, target, text and expiry checks,
then restoring only the specifically allowlisted action field. No shell, URL,
selector, filesystem or application-API action is added.
"""

from __future__ import annotations

from . import scale_action_contract as base


ACTION_PROFILE_VERSION = "scale-action-profile-v0.6.6"
NEW_KEY_CHORDS = frozenset({
    "Control+F", "Control+H", "Control+End", "Shift+End",
})


def validate_action(raw: str | dict, observation: base.Observation, *,
                    current_frame_id: str, now: float | None = None) -> dict:
    """Validate one old or new GUI action against the same current frame."""
    action = base._strict_json(raw)
    kind = action.get("type")
    if kind == "double_click":
        projected = {**action, "type": "click"}
        checked = base.validate_action(projected, observation,
                                       current_frame_id=current_frame_id,
                                       now=now)
        return {**checked, "type": "double_click"}
    if kind == "key" and type(action.get("key")) is str and action["key"] in NEW_KEY_CHORDS:
        projected = {**action, "key": "Control+S"}
        checked = base.validate_action(projected, observation,
                                       current_frame_id=current_frame_id,
                                       now=now)
        return {**checked, "key": action["key"]}
    if kind == "type" and "target" not in action:
        if action.get("mode") != "insert":
            raise base.ContractError("invalid_action")
        # A focused insertion is keyboard input to the current GUI focus, like
        # an untargeted key. The dummy point is used only to reuse the base
        # validator's exact schema/text/frame checks; it is never dispatched.
        projected = {**action, "target": {"x": 0, "y": 0}}
        checked = base.validate_action(projected, observation,
                                       current_frame_id=current_frame_id,
                                       now=now)
        return {key: value for key, value in checked.items() if key != "target"}
    return base.validate_action(action, observation,
                                current_frame_id=current_frame_id, now=now)


def public_receipt(observation: base.Observation, *, action: dict | None = None,
                   error: base.ContractError | None = None) -> dict:
    """Allowlisted log record with no typed text or private task instruction."""
    checked = (validate_action(action, observation,
                               current_frame_id=observation.frame_id,
                               now=observation.issued_at)
               if action is not None else None)
    projected = checked
    if checked is not None:
        if checked["type"] == "double_click":
            projected = {**checked, "type": "click"}
        elif checked["type"] == "key" and checked["key"] in NEW_KEY_CHORDS:
            projected = {**checked, "key": "Control+S"}
        elif checked["type"] == "type" and "target" not in checked:
            projected = {**checked, "target": {"x": 0, "y": 0}}
    result = base.public_receipt(observation, action=projected, error=error)
    result["action_profile"] = ACTION_PROFILE_VERSION
    if checked is not None:
        result["action_type"] = checked["type"]
    return result
