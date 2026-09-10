from typing import Literal

Direction = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
DirectionsMode = Literal["8", "4", "1"]
CameraAngle = Literal["high-top-down", "low-top-down", "side", "front"]
DetailLevel = Literal["low", "medium", "high", "simple", "balanced"]
OutlineStyle = Literal["black", "colored", "selective", "lineless", "none", "soft", "dark"]
ShadingStyle = Literal["none", "basic", "medium", "detailed"]
PaletteMode = Literal["generated", "project", "custom", "locked", "strict", "soft", "unlocked"]
BodyTemplate = Literal["bipedal", "semi-chibi-bipedal", "quadrupedal", "custom"]
AssetStatus = Literal["missing", "pending", "accepted", "rejected", "locked"]
JobStatus = Literal["queued", "generating", "processing", "completed", "failed"]
SeedMode = Literal["random", "reuse_base", "locked", "variation"]
RejectionReason = Literal[
    "wrong_identity",
    "wrong_clothing",
    "wrong_colors",
    "wrong_body_shape",
    "wrong_proportions",
    "wrong_direction",
    "wrong_pose",
    "wrong_spirit_form",
    "poor_pixel_quality",
    "too_much_detail",
    "too_little_detail",
    "custom",
]
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
MemoryKind = Literal["accepted", "rejected"]
