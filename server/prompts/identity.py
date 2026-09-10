from models.character import CharacterProfile


def identity_constraints(character: CharacterProfile) -> str:
    lock = character.identityLock
    parts: list[str] = []

    if character.species:
        parts.append(f"{character.species}")
    if character.bodyType:
        parts.append(f"{character.bodyType} body")

    if lock.lockFace:
        parts.append(f"same face and identity, distinctive face: {character.appearance}")
    elif character.appearance:
        parts.append(character.appearance)

    if lock.lockHair:
        parts.append("keep the same hair silhouette and color")
    if lock.lockClothing:
        parts.append(f"same clothing: {character.clothing}" if character.clothing else "same clothing")
    elif character.clothing:
        parts.append(character.clothing)
    if lock.lockBodyProportions:
        parts.append("lock body proportions, same height and mass")
    if lock.lockSilhouette:
        parts.append("preserve the character silhouette")
    if lock.lockPalette:
        parts.append("keep the same limited color palette")
    if lock.lockAccessories:
        parts.append("keep the same accessories and mantle details")

    spirit = character.spirit
    if spirit.enabled or lock.lockSpiritForm:
        spirit_bits = [spirit.notes] if spirit.notes else []
        if spirit.noLegs:
            spirit_bits.append("absolutely no human legs or boots")
        if spirit.mistFade:
            spirit_bits.append("lower body fades from the waist into spectral mist")
        if spirit.spectralTail:
            spirit_bits.append("floating spirit tail instead of legs")
        if spirit.auraColor:
            spirit_bits.append(f"subtle ghost aura {spirit.auraColor}, not evil, not undead")
        parts.append(", ".join(bit for bit in spirit_bits if bit))

    return ", ".join(part for part in parts if part)
