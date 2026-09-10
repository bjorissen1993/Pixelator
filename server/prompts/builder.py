from models.character import CharacterProfile, CharacterState
from models.enums import Direction, HeadVariant, LayerKind
from models.generation import PromptLayers
from prompts.direction import direction_prompt
from prompts.expression import expression_prompt
from prompts.global_style import global_style
from prompts.identity import identity_constraints
from prompts.state_prompts import state_prompt


def _join(parts: list[str]) -> str:
    return ", ".join(part.strip().strip(",") for part in parts if part and part.strip())


def build_prompt(
    character: CharacterProfile,
    state: CharacterState | None = None,
    direction: Direction | None = None,
    override: str = "",
    layer: LayerKind = "full",
    head_variant: HeadVariant | None = None,
    frame_index: int = 0,
    frame_count: int = 1,
) -> PromptLayers:
    layers = PromptLayers(
        globalStyle=global_style(character.camera, character.detail, character.outline, character.spriteSize),
        masterPrompt=character.masterPrompt,
        identity=identity_constraints(character),
        state=state_prompt(state) if state else "neutral full-body identity pose, canonical reference stance",
        direction=direction_prompt(direction, character.camera) if direction else "canonical front-south identity view",
        expression=expression_prompt(state, character.emotion) if state else f"default mood: {character.emotion.defaultMood}",
        override=override.strip(),
    )

    extras: list[str] = []
    if layer == "head":
        extras.append("head and shoulders portrait crop for a pixel sprite head layer, no full body")
    elif layer == "body":
        extras.append("body-only sprite, neck stump or empty neck joint, no head, keep body identity")
    if head_variant:
        extras.append(_head_variant_clause(head_variant))
    if frame_count > 1:
        extras.append(f"animation frame {frame_index + 1} of {frame_count}, same character, same costume, related pose")

    layers.final = _join(
        [
            layers.globalStyle,
            layers.masterPrompt,
            layers.identity,
            layers.state,
            layers.direction,
            layers.expression,
            layers.override,
            *extras,
        ]
    )
    return layers


def _head_variant_clause(variant: HeadVariant) -> str:
    return {
        "center": "head facing center, eyes forward",
        "left": "head turned left, not rotated as a 3D object, a distinct left-facing pixel head",
        "right": "head turned right, not rotated as a 3D object, a distinct right-facing pixel head",
        "slightUp": "head tilted slightly up, chin raised a little",
        "slightDown": "head tilted slightly down, gaze lowered a little",
    }[variant]
