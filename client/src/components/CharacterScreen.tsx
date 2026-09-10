import { APPLY_MODES, DEFAULT_SPRITE_SIZES } from "@shared";
import type { CharacterProfile, IdentityLock } from "@shared";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Area, Button, Field, PixelImage, Section, Select, TextInput, Toggle } from "./ui";

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
  const { character, selectedStateId, selectedDirection, busy, run, applyResult, setCharacter } = useWorkspace();
  const [draft, setDraft] = useState<CharacterProfile | null>(character);

  useEffect(() => setDraft(character), [character]);
  if (!character || !draft) return null;

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
      });
      setCharacter(saved);
    });

  const applyMaster = (applyMode: string) =>
    run("Updating master prompt", async () => {
      const result = await api.applyMasterPrompt(character.id, {
        masterPrompt: draft.masterPrompt,
        applyMode,
        stateId: selectedStateId,
        direction: selectedDirection,
      });
      if (result) applyResult(result);
    });

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
        </div>
        <Field label="Master prompt">
          <Area rows={5} value={draft.masterPrompt} onChange={(event) => set("masterPrompt", event.target.value)} />
        </Field>
        <p className="hint">
          Changing the master prompt never deletes accepted sprites. Choose how it should apply:
        </p>
        <div className="chip-row">
          {APPLY_MODES.map((mode) => (
            <Button key={mode} variant="secondary" onClick={() => applyMaster(mode)}>
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

      <Section title="Sprite settings">
        <div className="form-grid">
          <Field label="Camera">
            <Select value={draft.camera} onChange={(event) => set("camera", event.target.value as CharacterProfile["camera"])}>
              <option value="high-top-down">High top-down</option>
              <option value="low-top-down">Low top-down</option>
              <option value="front">Front</option>
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
              <option value="simple">Simple</option>
              <option value="balanced">Balanced</option>
              <option value="high">High</option>
            </Select>
          </Field>
          <Field label="Outline">
            <Select value={draft.outline} onChange={(event) => set("outline", event.target.value as CharacterProfile["outline"])}>
              <option value="none">None</option>
              <option value="soft">Soft</option>
              <option value="dark">Dark</option>
            </Select>
          </Field>
          <Field label="Palette colors">
            <TextInput
              type="number"
              min={8}
              max={128}
              value={draft.palette.colorCount}
              onChange={(event) => set("palette", { ...draft.palette, colorCount: Number(event.target.value) })}
            />
          </Field>
        </div>
        <Toggle
          label="Spirit form"
          checked={draft.spirit.enabled}
          onChange={(enabled) =>
            set("spirit", { ...draft.spirit, enabled, noLegs: enabled, spectralTail: enabled, mistFade: enabled })
          }
        />
        <Field label="Spirit notes">
          <Area rows={3} value={draft.spirit.notes} onChange={(event) => set("spirit", { ...draft.spirit, notes: event.target.value })} />
        </Field>
      </Section>

      <Section
        title="Reference sprite"
        actions={
          <div className="chip-row">
            <Button variant="secondary" onClick={() => run("Generating base", async () => {
              const result = await api.generateBase(character.id);
              if (result) applyResult(result);
            })}>
              Generate base
            </Button>
            <Button onClick={() => run("Accepting base", () => api.acceptBase(character.id).then(setCharacter))}>
              Accept as base
            </Button>
            <Button variant="secondary" onClick={() => run("Replacing base", () => api.replaceBase(character.id).then(setCharacter))}>
              Replace base
            </Button>
            <Button variant="ghost" onClick={() => run("Clearing reference", () => api.clearReference(character.id).then(setCharacter))}>
              Clear reference
            </Button>
            <Button variant="secondary" onClick={() => run("Generating variation", async () => {
              const result = await api.generateVariation(character.id);
              if (result) applyResult(result);
            })}>
              Generate variation
            </Button>
          </div>
        }
      >
        <div className="ref-row">
          <figure>
            <PixelImage path={character.pendingBase?.path} cacheKey={character.pendingBase?.createdAt} size={character.spriteSize} />
            <figcaption>Pending</figcaption>
          </figure>
          <figure>
            <PixelImage path={character.acceptedBase?.sprite.path} cacheKey={character.acceptedBase?.acceptedAt} size={character.spriteSize} />
            <figcaption>Accepted base</figcaption>
          </figure>
        </div>
      </Section>
    </div>
  );
}
