from domain.state_templates import template_by_id
from models.character import CharacterState


def state_prompt(state: CharacterState) -> str:
    template = template_by_id(state.baseType)
    base = template.prompt if template else f"{state.name} pose"
    if state.customPrompt.strip():
        return f"{base}, {state.customPrompt.strip()}"
    return base
