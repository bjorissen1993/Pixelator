"""Chimera project + Berwynn vertical-slice profiles.

These are test/config data for the isolated Asset Lab, not production Studio state.
"""

from __future__ import annotations

from models.catalog import AssetFlags, AssetProfile, GenerationSpec, ProjectProfile, StyleProfile, ValidatorRule

CHIMERA_PROJECT = ProjectProfile(
    id="chimera",
    name="Chimera",
    description="Vertical-slice project used to prove Pixelator's general asset pipeline.",
    styleProfileId="chimera-default",
    defaultAssetType="character",
    defaultAssetId="berwynn",
    isDefault=True,
)

CHIMERA_STYLE = StyleProfile(
    projectId="chimera",
    name="Chimera default",
    outline="black",
    shading="basic",
    detail="medium",
    paletteLimit=20,
    notes=["Project style rules stay here. They must not become global Pixelator rules."],
    validatorRules=[
        ValidatorRule(
            id="style_palette_limit",
            layer="project",
            message="Rejected: palette is too far from the Chimera style budget",
            enabled=False,
        )
    ],
)

BERWYNN_ASSET = AssetProfile(
    projectId="chimera",
    assetType="character",
    assetId="berwynn",
    name="Berwynn",
    canonicalKind="character_idle_front",
    canonicalLabel="Default idle / front reference (South for this character)",
    state="idle",
    direction="S",
    reviewChecklist=[
        "Single character only",
        "Full body, front-facing, centered, readable silhouette",
        "Elderly male spirit, short messy grey/white hair, thick beard",
        "Tired but kind stern face, broad slightly hunched shoulders",
        "Worn dark village tunic, faded chief mantle, simple cloth/leather belt",
        "No armor, no shoulder armor, no weapons",
        "Lower body fades into a spectral ghost tail — no legs, no boots",
        "Pale subtle blue spirit aura, melancholic protective presence",
        "Plain or transparent background",
    ],
    flags=AssetFlags(oneSubject=True, fullBody=True, plainBackground=True, spiritForm=True),
    generation=GenerationSpec(
        enabled=True,
        modelId="PublicPrompts/All-In-One-Pixel-Model",
        width=512,
        height=512,
        steps=30,
        guidance=7.5,
        prompt=(
            "pixelsprite, full body elderly male spirit, front facing, grey hair, thick grey beard, "
            "worn dark village tunic, faded mantle, spectral ghost tail instead of legs, "
            "no armor, no weapons, centered, plain background"
        ),
        negativePrompt=(
            "legs, boots, armor, helmet, shoulder pads, weapon, staff, portrait, cropped, "
            "multiple characters, spritesheet, busy background, realistic, 3d, text"
        ),
    ),
    validatorRules=[
        ValidatorRule(
            id="no_visible_legs",
            layer="asset",
            message="Rejected: legs are visible; this asset needs a spectral ghost tail",
        ),
        ValidatorRule(
            id="no_armor",
            layer="asset",
            message="Rejected: armor or shoulder pieces are visible",
        ),
        ValidatorRule(
            id="spectral_lower_body",
            layer="asset",
            message="Rejected: spectral lower body / ghost tail is missing",
        ),
    ],
)

STUB_ASSETS = [
    AssetProfile(
        projectId="chimera",
        assetType="item",
        assetId="rusted-fishing-trophy",
        name="Rusted Fishing Trophy",
        canonicalKind="item_default",
        canonicalLabel="Isolated default item sprite",
        reviewChecklist=["Isolated subject", "Readable at small size", "Plain background"],
        flags=AssetFlags(oneSubject=True, isolatedSubject=True, plainBackground=True),
    ),
    AssetProfile(
        projectId="chimera",
        assetType="tile",
        assetId="grass",
        name="Grass",
        canonicalKind="tile_base",
        canonicalLabel="Base tile / material reference",
        reviewChecklist=["Seamless edges", "Repeatable", "Style-consistent material"],
    ),
]


def builtin_projects() -> list[ProjectProfile]:
    return [CHIMERA_PROJECT]


def builtin_styles() -> list[StyleProfile]:
    return [CHIMERA_STYLE]


def builtin_assets() -> list[AssetProfile]:
    return [BERWYNN_ASSET, *STUB_ASSETS]
