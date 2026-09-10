from models.enums import Direction

EXPORT_ORDER: list[Direction] = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]

# Incremental 45-degree walks from South. N can be reached from both sides.
INCREMENTAL_CHAINS: list[list[Direction]] = [
    ["S", "SW", "W", "NW", "N"],
    ["S", "SE", "E", "NE", "N"],
]


def rotation_jobs(strategy: str, wanted: list[Direction]) -> list[tuple[Direction, Direction]]:
    """Return (from_direction, to_direction) pairs. South is never a target here."""
    selected = [direction for direction in EXPORT_ORDER if direction in wanted]
    if strategy == "incremental":
        jobs: list[tuple[Direction, Direction]] = []
        seen: set[Direction] = {"S"}
        for chain in INCREMENTAL_CHAINS:
            for index in range(1, len(chain)):
                target = chain[index]
                if target not in selected or target in seen:
                    continue
                jobs.append((chain[index - 1], target))
                seen.add(target)
        for direction in selected:
            if direction not in seen:
                jobs.append(("S", direction))
        return jobs
    return [("S", direction) for direction in selected if direction != "S"]
