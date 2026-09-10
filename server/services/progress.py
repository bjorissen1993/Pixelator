import threading

PIPELINE_STEPS = [
    "Generating South",
    "Generating rotations",
    "Applying palette",
    "Saving assets",
]

_lock = threading.Lock()
_state: dict[str, dict] = {}


def start(character_id: str, label: str) -> None:
    with _lock:
        _state[character_id] = {
            "active": True,
            "label": label,
            "step": PIPELINE_STEPS[0],
            "steps": list(PIPELINE_STEPS),
            "stepIndex": 0,
        }


def is_active(character_id: str) -> bool:
    with _lock:
        return bool(_state.get(character_id, {}).get("active"))


def set_step(character_id: str, step: str) -> None:
    with _lock:
        current = _state.get(character_id)
        if not current or not current.get("active"):
            return
        current["step"] = step
        if step in current["steps"]:
            current["stepIndex"] = current["steps"].index(step)


def finish(character_id: str) -> None:
    with _lock:
        current = _state.get(character_id)
        if not current:
            return
        current["active"] = False
        current["step"] = "done"
        current["stepIndex"] = len(current["steps"])


def get(character_id: str) -> dict:
    with _lock:
        current = _state.get(character_id)
        if not current:
            return {
                "active": False,
                "label": "",
                "step": "",
                "steps": list(PIPELINE_STEPS),
                "stepIndex": -1,
            }
        return dict(current)
