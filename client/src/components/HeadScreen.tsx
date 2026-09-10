import { HEAD_VARIANTS } from "@shared";
import { useMemo } from "react";
import { api } from "../api";
import { assetUrl } from "../asset";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button, Field, PixelImage, Section, TextInput } from "./ui";

export function HeadScreen() {
  const { character, selectedStateId, selectedDirection, run, applyResult, setCharacter, generating, busy } = useWorkspace();
  const state = character?.states.find((item) => item.id === selectedStateId);
  const slot = state?.directions.find((item) => item.direction === selectedDirection);
  const sprite = slot?.frames[0] ?? character?.acceptedBase?.sprite ?? character?.pendingBase;
  const scale = 8;

  const cross = useMemo(() => {
    if (!slot || !character) return { x: 0, y: 0 };
    return {
      x: (slot.headAnchor.headAnchorX + slot.headAnchor.headOffsetX) * scale,
      y: (slot.headAnchor.headAnchorY + slot.headAnchor.headOffsetY) * scale,
    };
  }, [slot, character, scale]);

  if (!character) return null;
  if (!state || !slot) return <p className="hint">Select a state and direction first.</p>;

  const setAnchor = (clientX: number, clientY: number, target: HTMLDivElement) => {
    const rect = target.getBoundingClientRect();
    const x = Math.max(0, Math.min(character.spriteSize - 1, Math.floor((clientX - rect.left) / scale)));
    const y = Math.max(0, Math.min(character.spriteSize - 1, Math.floor((clientY - rect.top) / scale)));
    run("Saving head anchor", () =>
      api
        .updateAnchors(character.id, {
          stateId: state.id,
          direction: selectedDirection,
          headAnchorX: x,
          headAnchorY: y,
          headOffsetX: slot.headAnchor.headOffsetX,
          headOffsetY: slot.headAnchor.headOffsetY,
        })
        .then(setCharacter),
    );
  };

  return (
    <div className="stack">
      <Section
        title="Head / body"
        actions={
          <Button
            disabled={generating || !!busy}
            onClick={() =>
              run("Generating head variants", async () => {
                const result = await api.generateHeadVariants(character.id, state.id, selectedDirection);
                if (result) applyResult(result);
              })
            }
          >
            Generate head variants
          </Button>
        }
      >
        <div className="head-layout">
          <div>
            <p className="hint">Click the sprite to set the neck anchor. No smooth rotation — variants are distinct pixel heads.</p>
            <div
              className="anchor-stage"
              style={{ width: character.spriteSize * scale, height: character.spriteSize * scale }}
              onClick={(event) => setAnchor(event.clientX, event.clientY, event.currentTarget)}
            >
              {sprite?.path ? (
                <img src={assetUrl(sprite.path, sprite.createdAt)} alt="body" className="pixel stage-img" />
              ) : (
                <div className="pixel-empty">No sprite</div>
              )}
              <span className="crosshair" style={{ left: cross.x, top: cross.y }} />
            </div>
          </div>
          <div className="stack">
            <div className="form-grid">
              <Field label="Anchor X">
                <TextInput value={slot.headAnchor.headAnchorX} readOnly />
              </Field>
              <Field label="Anchor Y">
                <TextInput value={slot.headAnchor.headAnchorY} readOnly />
              </Field>
              <Field label="Offset X">
                <TextInput
                  type="number"
                  value={slot.headAnchor.headOffsetX}
                  onChange={(event) =>
                    run("Saving offset", () =>
                      api
                        .updateAnchors(character.id, {
                          stateId: state.id,
                          direction: selectedDirection,
                          headAnchorX: slot.headAnchor.headAnchorX,
                          headAnchorY: slot.headAnchor.headAnchorY,
                          headOffsetX: Number(event.target.value),
                          headOffsetY: slot.headAnchor.headOffsetY,
                        })
                        .then(setCharacter),
                    )
                  }
                />
              </Field>
              <Field label="Offset Y">
                <TextInput
                  type="number"
                  value={slot.headAnchor.headOffsetY}
                  onChange={(event) =>
                    run("Saving offset", () =>
                      api
                        .updateAnchors(character.id, {
                          stateId: state.id,
                          direction: selectedDirection,
                          headAnchorX: slot.headAnchor.headAnchorX,
                          headAnchorY: slot.headAnchor.headAnchorY,
                          headOffsetX: slot.headAnchor.headOffsetX,
                          headOffsetY: Number(event.target.value),
                        })
                        .then(setCharacter),
                    )
                  }
                />
              </Field>
            </div>
            <div className="ref-row">
              <figure>
                <PixelImage asset={slot.body} size={character.spriteSize} scale={4} />
                <figcaption>Body</figcaption>
              </figure>
              <figure>
                <PixelImage asset={slot.head} size={character.spriteSize} scale={4} />
                <figcaption>Head</figcaption>
              </figure>
            </div>
            <p className="hint">
              Phaser metadata: blink={String(state.blinkingEnabled)}, talk mouths via talking frames, nod/shake via head
              variants, look-at-target={String(state.lookAtTargetEnabled)}.
            </p>
          </div>
        </div>
      </Section>
      <Section title="Head variants">
        <div className="card-grid">
          {HEAD_VARIANTS.map((variant) => (
            <figure key={variant} className="state-card">
              <PixelImage asset={slot.headVariants[variant]} size={character.spriteSize} scale={4} />
              <figcaption>{variant}</figcaption>
            </figure>
          ))}
        </div>
      </Section>
    </div>
  );
}
