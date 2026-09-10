from models.character import CharacterProfile

FRAMING_RETRY = (
    "pull the camera much farther back, full-body pixel art game sprite, entire character from head to spirit tail, "
    "complete silhouette with empty margin on every side, centered on the canvas, not a portrait, not a bust, "
    "not a close-up, no cropping, no clipped edges, one character only"
)

CROP_NEGATIVE = (
    "portrait, close-up, bust, upper body only, half body, cropped, cut off, clipped silhouette, "
    "missing lower body, missing spirit tail"
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
    if comp.entireSilhouetteVisible:
        parts.append("entire silhouette visible, nothing cut off by the frame")
    if comp.centerCharacter:
        parts.append("centered on canvas")
    if comp.fitSafeMargins:
        parts.append("fits fully inside the frame with visible padding")
    if comp.preventCropping:
        parts.append("no cropping")
    if comp.preventPortrait or comp.noPortraitCloseup:
        parts.append("not a portrait, not a bust")
    if comp.preventCloseup or comp.noPortraitCloseup:
        parts.append("not close-up")
    if comp.oneCharacterOnly:
        parts.append("one character only")
    if character.spirit.enabled or character.spirit.noLegs:
        if comp.showFullSpiritBody or comp.showFullSpiritTail:
            parts.append("full lower spirit body visible, full floating spirit tail in frame")
    if stronger:
        parts.append(FRAMING_RETRY)
    return ", ".join(parts)


def composition_negative(character: CharacterProfile) -> str:
    comp = character.composition
    if not (
        comp.fullBodySprite
        or comp.preventCropping
        or comp.preventPortrait
        or comp.preventCloseup
        or comp.noPortraitCloseup
        or comp.showFullSpiritBody
        or comp.showFullSpiritTail
    ):
        return ""
    parts = [CROP_NEGATIVE]
    if character.spirit.enabled or character.spirit.noLegs or character.spirit.spectralTail:
        parts.append("missing spectral tail, cropped ghost body, legs instead of spirit tail")
    if comp.oneCharacterOnly:
        parts.append("two characters, extra person, crowd")
    return ", ".join(parts)
