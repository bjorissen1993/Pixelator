from datetime import datetime, timezone
from uuid import uuid4

from domain.directions import directions_for_mode
from domain.state_templates import template_by_id
from models.character import (
    CharacterProfile,
    CharacterState,
    CompositionSettings,
    DirectionSlot,
    EmotionProfile,
    HeadAnchor,
    IdentityLock,
    PaletteSettings,
    SpiritSettings,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid4().hex


def make_state_from_template(template_id: str, sprite_size: int) -> CharacterState | None:
    template = template_by_id(template_id)
    if template is None:
        return None
    selected = directions_for_mode(template.directionsMode)
    default_anchor = HeadAnchor(headAnchorX=sprite_size // 2, headAnchorY=max(8, sprite_size // 3))
    return CharacterState(
        id=new_id(),
        name=template.name,
        baseType=template.baseType,
        customPrompt="",
        directionsMode=template.directionsMode,
        selectedDirections=list(selected),
        frameCount=template.frameCount,
        loop=template.loop,
        animationSpeed=template.animationSpeed,
        kind=template.kind,
        createdAt=utc_now(),
        directions=[
            DirectionSlot(direction=direction, headAnchor=default_anchor.model_copy())
            for direction in selected
        ],
    )


def berwynn_profile() -> CharacterProfile:
    now = utc_now()
    sprite_size = 48
    idle = make_state_from_template("idle", sprite_size)
    assert idle is not None
    return CharacterProfile(
        id=new_id(),
        slug="berwynn",
        name="Berwynn",
        masterPrompt=(
            "Berwynn, elderly former village chief spirit, short messy grey hair, thick rough grey beard, "
            "weathered face, stern but kind, tired eyes, broad shoulders, slightly hunched, worn dark village tunic, "
            "faded chief mantle, simple cloth and leather belt, practical village clothing, no armor, legless ghost, "
            "lower body fades from the waist into spectral mist, floating spirit tail, pale blue subtle ghost aura, "
            "not evil, not undead, melancholic protector"
        ),
        appearance=(
            "short messy grey hair, thick rough grey beard, weathered face, stern but kind, tired eyes, "
            "broad shoulders, slightly hunched"
        ),
        clothing="worn dark village tunic, faded chief mantle, simple cloth/leather belt, practical village clothing, no armor",
        bodyType="elderly, broad-shouldered, slightly hunched, spirit lower body",
        species="human spirit",
        spirit=SpiritSettings(
            enabled=True,
            noLegs=True,
            spectralTail=True,
            mistFade=True,
            auraColor="#9ecbff",
            notes="no legs, no boots, lower body fades from waist into spectral mist, floating spirit tail, pale blue subtle ghost aura, not evil or undead-looking",
        ),
        spriteSize=sprite_size,
        camera="high-top-down",
        palette=PaletteSettings(colorCount=20, locked=False, colors=[]),
        outline="black",
        shading="basic",
        detail="medium",
        negativePrompt="no armor, no legs, no boots, no weapons unless requested, no realistic rendering, no smooth gradients, no modern clothing",
        bodyTemplate="custom",
        paletteMode="generated",
        identityLock=IdentityLock(),
        composition=CompositionSettings(
            fullBodySprite=True,
            entireSilhouetteVisible=True,
            preventCropping=True,
            preventPortrait=True,
            preventCloseup=True,
            centerCharacter=True,
            fitSafeMargins=True,
            oneCharacterOnly=True,
            showFullSpiritBody=True,
            showFullSpiritTail=True,
            noPortraitCloseup=True,
        ),
        emotion=EmotionProfile(
            expressiveness="low",
            bodyMovement="subtle",
            facialRange="limited",
            defaultMood="stern, tired, protective",
            laughterStyle="restrained, rare, warm",
            sadnessStyle="internal, heavy",
            angerStyle="slow-burning, contained, protective",
            talkingStyle="slow, calm, thoughtful",
            customEmotionNotes="Never slapstick. Emotion lives in the eyes, beard, and shoulders more than the mouth.",
        ),
        states=[idle],
        createdAt=now,
        updatedAt=now,
    )
