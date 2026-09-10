from models.enums import CameraAngle, Direction

_FRONT = {
    "N": "facing away from camera, clear back view",
    "NE": "facing away, three-quarter back-right view",
    "E": "facing right, full side profile",
    "SE": "facing toward camera, three-quarter front-right view",
    "S": "facing camera, full front view",
    "SW": "facing toward camera, three-quarter front-left view",
    "W": "facing left, full side profile",
    "NW": "facing away, three-quarter back-left view",
}

_TOP_DOWN = {
    "N": "moving north, top of head toward the top of the canvas, back mostly visible",
    "NE": "moving north-east, diagonal top-down, back-right of the body visible",
    "E": "moving east, right side visible from overhead",
    "SE": "moving south-east, diagonal top-down, front-right visible",
    "S": "moving south, face and chest more visible from overhead",
    "SW": "moving south-west, diagonal top-down, front-left visible",
    "W": "moving west, left side visible from overhead",
    "NW": "moving north-west, diagonal top-down, back-left of the body visible",
}


def direction_prompt(direction: Direction, camera: CameraAngle) -> str:
    table = _FRONT if camera == "front" else _TOP_DOWN
    return f"{direction} direction, {table[direction]}, same character, same costume, same proportions"
