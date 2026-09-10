from models.character import CharacterProfile

FRAMING_RETRY = (
    "pull the camera back, full-body pixel art sprite, entire character visible with empty margin, "
    "complete silhouette inside the frame, centered game sprite, not a portrait, not a bust, not a close-up, "
    "no cropping, no clipped edges"
)

CROP_NEGATIVE = (
    "cropped, close-up, portrait, bust, upper body only, half body, zoomed in, "
    "cut off silhouette, clipped sprite, missing lower body, missing spirit tail"
)


def composition_constraints(character: CharacterProfile, stronger: bool = False) -> str:
    comp = character.composition
    parts: list[str] = []
    if comp.fullBodySprite:
        parts.extend(
            [
                "full-body pixel art sprite",
                "entire character visible",
                "complete silhouette visible",
                "game-ready sprite",
            ]
        )
        if comp.centerCharacter:
            parts.append("centered on canvas")
        if comp.fitSafeMargins:
            parts.append("fits fully inside the frame with visible padding")
        if comp.preventCropping:
            parts.append("no cropping")
        if comp.noPortraitCloseup:
            parts.extend(["not a portrait", "not a bust", "not close-up"])
        if (comp.showFullSpiritTail or character.spirit.spectralTail) and (
            character.spirit.enabled or character.spirit.noLegs
        ):
            parts.append("full spirit tail visible, spectral lower body fully in frame")
    if stronger:
        parts.append(FRAMING_RETRY)
    return ", ".join(parts)


def composition_negative(character: CharacterProfile) -> str:
    comp = character.composition
    if not (comp.fullBodySprite or comp.preventCropping or comp.noPortraitCloseup):
        return ""
    parts = [CROP_NEGATIVE]
    if character.spirit.enabled or character.spirit.noLegs or character.spirit.spectralTail:
        parts.append("missing spectral tail, cropped ghost body, legs instead of spirit tail")
    return ", ".join(parts)
