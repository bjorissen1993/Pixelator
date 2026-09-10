from models.enums import Direction, DirectionsMode

DIRECTIONS_8: list[Direction] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
DIRECTIONS_4: list[Direction] = ["N", "E", "S", "W"]
DIRECTIONS_1: list[Direction] = ["S"]
EXPORT_DIRECTION_ORDER: list[Direction] = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]
HEAD_VARIANTS = ["center", "left", "right", "slightUp", "slightDown"]


def directions_for_mode(mode: DirectionsMode) -> list[Direction]:
    if mode == "8":
        return list(DIRECTIONS_8)
    if mode == "4":
        return list(DIRECTIONS_4)
    return list(DIRECTIONS_1)


def ordered_for_export(selected: list[Direction]) -> list[Direction]:
    selected_set = set(selected)
    return [d for d in EXPORT_DIRECTION_ORDER if d in selected_set]
