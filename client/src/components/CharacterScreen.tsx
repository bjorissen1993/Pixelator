import { APPLY_MODES, DEFAULT_SPRITE_SIZES } from "@shared";
import type { CharacterProfile, CompositionSettings, IdentityLock } from "@shared";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { BaseCompositionPanel } from "./BaseCompositionPanel";
import { canAcceptAsBase, invalidBaseReasons } from "../baseValidation";
import { Area, Button, Field, Section, Select, SpritePreviewCard, TextInput, Toggle } from "./ui";

const COMPOSITION_DEFAULTS: CompositionSettings = {
  fullBodySprite: true,
  entireSilhouetteVisible: true,
  preventCropping: true,
  preventPortrait: true,
  preventCloseup: true,
  centerCharacter: true,
  fitSafeMargins: true,
  oneCharacterOnly: true,
  showFullSpiritBody: true,
  showFullSpiritTail: true,
  noPortraitCloseup: true,
};

const COMPOSITION_LABELS: Array<[keyof CompositionSettings, string]> = [
  ["fullBodySprite", "Full body sprite"],
  ["entireSilhouetteVisible", "Entire silhouette visible"],
  ["preventCropping", "Prevent cropping"],
  ["preventPortrait", "Prevent portrait composition"],
  ["preventCloseup", "Prevent close-up"],
  ["centerCharacter", "Center character on canvas"],
  ["fitSafeMargins", "Fit within safe margins"],
  ["oneCharacterOnly", "One character only"],
  ["showFullSpiritBody", "For spirit characters: show full lower spirit body"],
  ["showFullSpiritTail", "For spirit characters: show full spirit tail"],
];

const LOCK_LABELS: Array<[keyof IdentityLock, string]> = [
  ["lockFace", "Face"],
  ["lockHair", "Hair"],
  ["lockClothing", "Clothing"],
  ["lockPalette", "Palette"],
  ["lockBodyProportions", "Body proportions"],
  ["lockSilhouette", "Silhouette"],
  ["lockSpiritForm", "Spirit form"],
  ["lockAccessories", "Accessories"],
];

export function CharacterScreen() {
  const { character, selectedStateId, selectedDirection, busy, generating, progress, run, applyResult, setCharacter } = useWorkspace();
  const [draft, setDraft] = useState<CharacterProfile | null>(character);

  useEffect(() => {
    if (!character) {
      setDraft(null);
      return;
    }
    setDraft({
      ...character,
      composition: { ...COMPOSITION_DEFAULTS, ...character.composition },
    });
  }, [character]);
  if (!character || !draft) return null;
  const locked = generating || !!busy;
  const pendingInvalid = invalidBaseReasons(character.pendingBase?.validation);
  const acceptDisabled = locked || !canAcceptAsBase(character.pendingBase);

  const set = <K extends keyof CharacterProfile>(key: K, value: CharacterProfile[K]) =>
    setDraft({ ...draft, [key]: value });

  const save = () =>
    run("Saving profile", async () => {
      const saved = await api.patchCharacter(character.id, {
        name: draft.name,
        masterPrompt: draft.masterPrompt,
        appearance: draft.appearance,
        clothing: draft.clothing,
        bodyType: draft.bodyType,
        species: draft.species,
        spirit: draft.spirit,
        spriteSize: draft.spriteSize,
        camera: draft.camera,
        palette: draft.palette,
        outline: draft.outline,
        detail: draft.detail,
        seed: draft.seed,
        seedLocked: draft.seedLocked,
        negativePrompt: draft.negativePrompt,
        shading: draft.shading,
        paletteMode: draft.paletteMode,
        bodyTemplate: draft.bodyTemplate,
        composition: draft.composition,
      });
      setCharacter(saved);
    });

  const applyMaster = (applyMode: string) =>
    run(
      "Updating master prompt",
      async () => {
        const result = await api.applyMasterPrompt(character.id, {
          masterPrompt: draft.masterPrompt,
          applyMode,
          stateId: selectedStateId,
          direction: selectedDirection,
        });
        if (result) applyResult(result);
      },
      { generating: applyMode !== "future_only" },
    );

  return (
    <div className="stack">
      <Section
        title="Identity"
        actions={
          <Button onClick={save} disabled={!!busy}>
            Save profile
          </Button>
        }
      >
        <div className="form-grid">
          <Field label="Name">
            <TextInput value={draft.name} onChange={(event) => set("name", event.target.value)} />
          </Field>
          <Field label="Species / type">
            <TextInput value={draft.species} onChange={(event) => set("species", event.target.value)} />
          </Field>
          <Field label="Body type">
            <TextInput value={draft.bodyType} onChange={(event) => set("bodyType", event.target.value)} />
          </Field>
          <Field label="Seed">
            <TextInput
              type="number"
              value={draft.seed ?? ""}
              onChange={(event) => set("seed", event.target.value === "" ? null : Number(event.target.value))}
            />
          </Field>
          <Field label="Body template">
            <Select value={draft.bodyTemplate ?? "custom"} onChange={(event) => set("bodyTemplate", event.target.value as CharacterProfile["bodyTemplate"])}>
              <option value="bipedal">Bipedal</option>
              <option value="semi-chibi-bipedal">Semi-chibi bipedal</option>
              <option value="quadrupedal">Quadrupedal</option>
              <option value="custom">Custom</option>
            </Select>
          </Field>
        </div>
        <Field label="Master prompt">
          <Area rows={5} value={draft.masterPrompt} onChange={(event) => set("masterPrompt", event.target.value)} />
        </Field>
        <Field label="Negative description">
          <Area rows={3} value={draft.negativePrompt ?? ""} onChange={(event) => set("negativePrompt", event.target.value)} />
        </Field>
        <p className="hint">
          Changing the master prompt never deletes accepted sprites. Choose how it should apply:
        </p>
        <div className="chip-row">
          {APPLY_MODES.map((mode) => (
            <Button key={mode} variant="secondary" disabled={!!busy} onClick={() => applyMaster(mode)}>
              {mode.replaceAll("_", " ")}
            </Button>
          ))}
        </div>
        <Field label="Appearance">
          <Area rows={3} value={draft.appearance} onChange={(event) => set("appearance", event.target.value)} />
        </Field>
        <Field label="Clothing">
          <Area rows={3} value={draft.clothing} onChange={(event) => set("clothing", event.target.value)} />
        </Field>
      </Section>

      <Section title="Identity lock">
        <div className="lock-grid">
          {LOCK_LABELS.map(([key, label]) => (
            <Toggle
              key={key}
              label={label}
              checked={draft.identityLock[key]}
              onChange={(value) => {
                const identityLock = { ...draft.identityLock, [key]: value };
                setDraft({ ...draft, identityLock });
                run("Saving lock", () => api.patchCharacter(character.id, { identityLock }).then(setCharacter));
              }}
            />
          ))}
        </div>
      </Section>

      <Section title="Composition">
        <p className="hint">
          Framing controls for game-ready full-body sprites. Invalid portrait or cropped bases cannot be accepted.
          When Prevent cropping and Full body sprite are on, failed bases retry with stronger framing.
        </p>
        <div className="lock-grid">
          {COMPOSITION_LABELS.map(([key, label]) => (
            <Toggle
              key={key}
              label={label}
              checked={draft.composition?.[key] ?? true}
              onChange={(value) => {
                const composition = { ...COMPOSITION_DEFAULTS, ...draft.composition, [key]: value };
                if (key === "preventPortrait" || key === "preventCloseup") {
                  composition.noPortraitCloseup = composition.preventPortrait && composition.preventCloseup;
                }
                setDraft({ ...draft, composition });
              }}
            />
          ))}
        </div>
      </Section>

      <Section title="Sprite settings">
        <div className="form-grid">
          <Field label="Camera">
            <Select value={draft.camera} onChange={(event) => set("camera", event.target.value as CharacterProfile["camera"])}>
              <option value="high-top-down">High top-down</option>
              <option value="low-top-down">Low top-down</option>
              <option value="side">Side</option>
            </Select>
          </Field>
          <Field label="Sprite size">
            <Select value={draft.spriteSize} onChange={(event) => set("spriteSize", Number(event.target.value))}>
              {DEFAULT_SPRITE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}×{size}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Detail">
            <Select value={draft.detail} onChange={(event) => set("detail", event.target.value as CharacterProfile["detail"])}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </Select>
          </Field>
          <Field label="Outline">
            <Select value={draft.outline} onChange={(event) => set("outline", event.target.value as CharacterProfile["outline"])}>
              <option value="black">Black</option>
              <option value="colored">Colored</option>
              <option value="selective">Selective</option>
              <option value="lineless">Lineless</option>
            </Select>
          </Field>
          <Field label="Shading">
            <Select value={draft.shading ?? "basic"} onChange={(event) => set("shading", event.target.value as CharacterProfile["shading"])}>
              <option value="none">None</option>
              <option value="basic">Basic</option>
              <option value="medium">Medium</option>
              <option value="detailed">Detailed</option>
            </Select>
          </Field>
          <Field label="Palette mode">
            <Select value={draft.paletteMode ?? "generated"} onChange={(event) => set("paletteMode", event.target.value as CharacterProfile["paletteMode"])}>
              <option value="unlocked">Unlocked</option>
              <option value="soft">Soft palette lock</option>
              <option value="strict">Strict palette lock</option>
              <option value="generated">Generated (unlocked)</option>
              <option value="project">Project palette</option>
              <option value="custom">Custom palette</option>
              <option value="locked">Locked (strict)</option>
            </Select>
          </Field>
          <Field label="Palette colors">
            <TextInput
              type="number"
              min={8}
              max={64}
              value={draft.palette.colorCount}
              onChange={(event) => set("palette", { ...draft.palette, colorCount: Number(event.target.value) })}
            />
          </Field>
          <p className="hint">48×48 sprites stay readable around 16–24 colors. More colors turn into muddy speckle.</p>
        </div>
        <Toggle
          label="Lock seed"
          checked={draft.seedLocked ?? false}
          onChange={(value) => set("seedLocked", value)}
        />
        <Toggle
          label="Spirit form"
          checked={draft.spirit.enabled}
          onChange={(enabled) =>
            setDraft({
              ...draft,
              spirit: { ...draft.spirit, enabled, noLegs: enabled, spectralTail: enabled, mistFade: enabled },
              composition: {
                ...draft.composition,
                showFullSpiritTail: enabled ? true : draft.composition.showFullSpiritTail,
                showFullSpiritBody: enabled ? true : draft.composition.showFullSpiritBody,
              },
            })
          }
        />
        <Field label="Spirit notes">
          <Area rows={3} value={draft.spirit.notes} onChange={(event) => set("spirit", { ...draft.spirit, notes: event.target.value })} />
        </Field>
      </Section>

      <Section title="Reference sprites">
        <p className="hint">
          Pending is the latest generated candidate. Accepted base is the locked identity reference used for later
          generations. Previews are nearest-neighbour enlargements of the true sprite.
        </p>
        <div className="ref-row">
          <SpritePreviewCard
            key={character.pendingBase?.id ?? "pending-empty"}
            title="Pending Sprite"
            empty="No pending sprite"
            asset={character.pendingBase}
            loading={generating}
            progress={progress}
            actions={
              <>
                <Button
                  disabled={locked}
                  onClick={() =>
                    run("Generating base", async () => {
                      const result = await api.generateBase(character.id);
                      if (result) applyResult(result);
                    })
                  }
                >
                  Generate base
                </Button>
                <Button
                  disabled={acceptDisabled}
                  onClick={() => run("Accepting base", () => api.acceptBase(character.id).then(setCharacter), { generating: false })}
                >
                  Accept as base
                </Button>
                <Button
                  variant="ghost"
                  disabled={locked || !character.pendingBase}
                  onClick={() => run("Discarding pending", () => api.discardPending(character.id).then(setCharacter), { generating: false })}
                >
                  Discard
                </Button>
                <Button
                  variant="secondary"
                  disabled={locked || !character.acceptedBase}
                  onClick={() =>
                    run("Generating variation", async () => {
                      const result = await api.generateVariation(character.id);
                      if (result) applyResult(result);
                    })
                  }
                >
                  Generate variation
                </Button>
              </>
            }
          />
          <SpritePreviewCard
            key={character.acceptedBase?.sprite.id ?? "accepted-empty"}
            title="Accepted Base"
            empty="No accepted base"
            asset={character.acceptedBase?.sprite}
            actions={
              <>
                <Button
                  variant="secondary"
                  disabled={acceptDisabled}
                  onClick={() => run("Replacing base", () => api.replaceBase(character.id).then(setCharacter), { generating: false })}
                >
                  Replace base
                </Button>
                <Button
                  variant="ghost"
                  disabled={locked || !character.acceptedBase}
                  onClick={() => run("Clearing reference", () => api.clearReference(character.id).then(setCharacter), { generating: false })}
                >
                  Clear reference
                </Button>
              </>
            }
          />
        </div>
        {pendingInvalid.length ? (
          <ul className="quality-warnings invalid-base">
            {pendingInvalid.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : character.pendingBase?.validation?.warnings?.length ? (
          <ul className="quality-warnings">
            {character.pendingBase.validation.warnings.map((warning) => (
              <li key={warning.code}>{warning.message}</li>
            ))}
          </ul>
        ) : null}
        <BaseCompositionPanel asset={character.pendingBase} />
      </Section>
    </div>
  );
}
