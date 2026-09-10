from models.enums import Direction, DirectionsMode

DIRECTIONS_8: list[Direction] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
DIRECTIONS_4: list[Direction] = ["N", "E", "S", "W"]
DIRECTIONS_1: list[Direction] = ["S"]
EXPORT_DIRECTION_ORDER: list[Direction] = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]
HEAD_VARIANTS = ["center", "left", "right", "slightUp", "slightDown"]

NEIGHBORS: dict[Direction, list[Direction]] = {
    "S": ["SW", "SE", "W", "E", "N"],
    "SW": ["S", "W", "SE", "NW"],
    "W": ["SW", "NW", "S", "N"],
    "NW": ["W", "N", "SW", "NE"],
    "N": ["NW", "NE", "W", "E", "S"],
    "NE": ["N", "E", "NW", "SE"],
    "E": ["NE", "SE", "N", "S"],
    "SE": ["E", "S", "NE", "SW"],
}


def directions_for_mode(mode: DirectionsMode) -> list[Direction]:
    if mode == "8":
        return list(DIRECTIONS_8)
    if mode == "4":
        return list(DIRECTIONS_4)
    return list(DIRECTIONS_1)


def ordered_for_export(selected: list[Direction]) -> list[Direction]:
    selected_set = set(selected)
    return [d for d in EXPORT_DIRECTION_ORDER if d in selected_set]


def closest_reference(target: Direction, available: list[Direction]) -> Direction | None:
    have = set(available)
    for neighbor in NEIGHBORS.get(target, []):
        if neighbor in have:
            return neighbor
    if "S" in have and target != "S":
        return "S"
    return None
