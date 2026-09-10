from models.character import CharacterProfile, CharacterState
from models.enums import Direction, HeadVariant, LayerKind
from models.generation import PromptLayers
from prompts.direction import direction_prompt
from prompts.expression import expression_prompt
from prompts.global_style import global_style
from prompts.identity import hard_constraints, identity_constraints
from prompts.state_prompts import state_prompt

DEFAULT_NEGATIVE = (
    "3D render, realistic painting, smooth gradients, PBR, photographic, extra limbs, legs, boots, armor, "
    "weapon unless requested, blurry, anti-aliased, different outfit, different hair, different beard, "
    "photorealistic, dithering, noisy speckles, jpeg artifacts, painterly, extra characters, scenery, text, watermark"
)


def _join(parts: list[str]) -> str:
    return ", ".join(part.strip().strip(",") for part in parts if part and part.strip())


def build_negative(character: CharacterProfile) -> str:
    parts = [DEFAULT_NEGATIVE, character.negativePrompt]
    if character.spirit.enabled or character.spirit.noLegs:
        parts.append("human legs, boots, feet, armor, weapons unless requested, bipedal standing pose")
    return _join(parts)


def build_prompt(
    character: CharacterProfile,
    state: CharacterState | None = None,
    direction: Direction | None = None,
    override: str = "",
    layer: LayerKind = "full",
    head_variant: HeadVariant | None = None,
    frame_index: int = 0,
    frame_count: int = 1,
    from_direction: Direction | None = None,
    action: str = "",
    embed_negative: bool = True,
    extra_clauses: list[str] | None = None,
) -> PromptLayers:
    visual = global_style(
        character.camera,
        character.detail,
        character.outline,
        character.shading,
        character.bodyTemplate,
        character.spriteSize,
    )
    identity = identity_constraints(character)
    constraints = hard_constraints(character)
    layers = PromptLayers(
        globalStyle=visual,
        visualStyle=visual,
        masterPrompt=character.masterPrompt,
        identity=identity,
        hardConstraints=constraints,
        state=state_prompt(state) if state else "neutral full-body identity pose, canonical reference stance",
        direction=direction_prompt(direction, character.camera, from_direction)
        if direction
        else "canonical front-south identity view",
        expression=expression_prompt(state, character.emotion)
        if state
        else f"default mood: {character.emotion.defaultMood}",
        override=override.strip(),
        negative=build_negative(character),
    )

    extras: list[str] = list(extra_clauses or [])
    if layer == "head":
        extras.append("head and shoulders portrait crop for a pixel sprite head layer, no full body")
    elif layer == "body":
        extras.append("body-only sprite, neck stump or empty neck joint, no head, keep body identity")
    if head_variant:
        extras.append(_head_variant_clause(head_variant))
    if action:
        extras.append(action)
    if frame_count > 1:
        extras.append(f"animation frame {frame_index + 1} of {frame_count}, same character, same costume, related pose")
    if embed_negative and layers.negative:
        extras.append(f"avoid: {layers.negative}")

    layers.final = _join(
        [
            layers.identity,
            layers.visualStyle,
            layers.masterPrompt,
            layers.direction,
            layers.state,
            layers.hardConstraints,
            layers.expression,
            layers.override,
            *extras,
        ]
    )
    return layers


def build_pixellab_description(character: CharacterProfile, override: str = "") -> str:
    parts = [character.masterPrompt]
    if character.appearance:
        parts.append(character.appearance)
    if character.clothing:
        parts.append(character.clothing)
    if character.bodyType:
        parts.append(character.bodyType)
    spirit = character.spirit
    if spirit.enabled or spirit.noLegs:
        parts.append(spirit.notes or "legless ghost, no legs, no boots, lower body fades into spectral mist, floating spirit tail")
    parts.append(hard_constraints(character))
    if override.strip():
        parts.append(override.strip())
    return _join(parts)[:2000]


def _head_variant_clause(variant: HeadVariant) -> str:
    return {
        "center": "head facing center, eyes forward",
        "left": "head turned left, not rotated as a 3D object, a distinct left-facing pixel head",
        "right": "head turned right, not rotated as a 3D object, a distinct right-facing pixel head",
        "slightUp": "head tilted slightly up, chin raised a little",
        "slightDown": "head tilted slightly down, gaze lowered a little",
    }[variant]
