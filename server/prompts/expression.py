from models.character import CharacterState, EmotionProfile

_STATE_STYLE_ATTR = {
    "laughing": "laughterStyle",
    "sad": "sadnessStyle",
    "angry": "angerStyle",
    "talking": "talkingStyle",
    "happy": "defaultMood",
    "worried": "defaultMood",
    "surprised": "defaultMood",
    "thinking": "defaultMood",
    "waving": "talkingStyle",
    "idle": "defaultMood",
    "sitting": "defaultMood",
    "walk": "defaultMood",
    "floatingIdle": "defaultMood",
    "materialize": "defaultMood",
    "fadeOut": "defaultMood",
    "memoryEcho": "defaultMood",
}


def expression_prompt(state: CharacterState, emotion: EmotionProfile) -> str:
    attr = _STATE_STYLE_ATTR.get(state.baseType, "defaultMood")
    style = getattr(emotion, attr)
    parts = [
        f"default mood: {emotion.defaultMood}",
        f"{emotion.expressiveness} expressiveness",
        f"{emotion.bodyMovement} body movement",
        f"{emotion.facialRange} facial range",
        f"this state's emotion language: {style}",
    ]
    if emotion.customEmotionNotes:
        parts.append(emotion.customEmotionNotes)
    if emotion.expressiveness == "low":
        parts.append("keep the pose restrained, avoid cartoon exaggeration")
    elif emotion.expressiveness == "high":
        parts.append("allow a broader pose, still the same character")
    return ", ".join(parts)
