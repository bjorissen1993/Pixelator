from typing import Literal

Direction = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
DirectionsMode = Literal["8", "4", "1"]
CameraAngle = Literal["high-top-down", "low-top-down", "front"]
DetailLevel = Literal["simple", "balanced", "high"]
OutlineStyle = Literal["none", "soft", "dark"]
Expressiveness = Literal["low", "medium", "high"]
BodyMovement = Literal["subtle", "natural", "animated"]
FacialRange = Literal["limited", "balanced", "broad"]
HeadVariant = Literal["center", "left", "right", "slightUp", "slightDown"]
SpriteKind = Literal["full", "body", "head", "overlay"]
StateKind = Literal["static", "animated"]
LayerKind = Literal["full", "body", "head"]
ApplyMode = Literal[
    "future_only",
    "regenerate_current_state",
    "regenerate_selected_direction",
    "regenerate_all_states",
    "regenerate_head_layers",
]
WarningSeverity = Literal["warning", "error"]
