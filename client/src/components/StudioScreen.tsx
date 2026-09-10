import { EXPORT_DIRECTION_ORDER, FRAME_COUNTS, REJECTION_REASONS } from "@shared";
import type { Direction, DirectionSlot, RejectionReason } from "@shared";
import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button, PixelImage, Select, SpritePreviewCard, TextInput } from "./ui";

const GRID: Array<Direction | "REF"> = ["NW", "N", "NE", "W", "REF", "E", "SW", "S", "SE"];

function slotStatus(slot?: DirectionSlot) {
  if (!slot) return "missing";
  if (slot.locked) return "locked";
  if (slot.status && slot.status !== "missing") return slot.status;
  return slot.frames[0] ? "pending" : "missing";
}

export function StudioScreen() {
  const {
    character,
    selectedStateId,
    selectedDirection,
    setSelectedStateId,
    setSelectedDirection,
    setSection,
    generating,
    busy,
    progress,
    run,
    applyResult,
    setCharacter,
    templates,
  } = useWorkspace();
  if (!character) return null;
  const state = character.states.find((item) => item.id === selectedStateId) ?? character.states[0];
  const locked = generating || !!busy;
  const selectedSlot = state?.directions.find((item) => item.direction === selectedDirection);

  const generateEight = () => {
    if (!state) return;
    run("Generate 8 Directions", async () => {
      const started = await api.generateDirectionSet(character.id, { stateId: state.id, useReference: true });
      return started;
    });
  };

  return (
    <div className="studio">
      <div className="studio-main">
        <section className="studio-hero">
          <div>
            <p className="eyebrow">Visual workspace</p>
            <h2>{character.name}</h2>
            <p>
              {character.species} · {character.camera} · {character.outline} outline · {character.shading} shading ·{" "}
              {character.spriteSize}px
              {character.acceptedBase ? " · identity locked" : " · accept a base to condition directions"}
            </p>
          </div>
          <div className="chip-row">
            <Button disabled={locked} onClick={() => run("Generating base", async () => {
              const result = await api.generateBase(character.id, { seedMode: character.seedLocked ? "locked" : "random" });
              if (result) applyResult(result);
            })}>
              Generate Base
            </Button>
            <Button
              disabled={locked || !character.acceptedBase || !state}
              onClick={generateEight}
            >
              Generate 8 Directions
            </Button>
          </div>
        </section>

        <div className="ref-row">
          <SpritePreviewCard
            title="Pending Sprite"
            empty="No pending sprite"
            asset={character.pendingBase}
            loading={generating && !progress?.currentItem}
            progress={progress}
            actions={
              <>
                <Button disabled={locked || !character.pendingBase} onClick={() => run("Accepting base", () => api.acceptBase(character.id).then(setCharacter), { generating: false })}>
                  Accept as Base
                </Button>
                <Button variant="ghost" disabled={locked || !character.pendingBase} onClick={() => run("Discarding pending", () => api.discardPending(character.id).then(setCharacter), { generating: false })}>
                  Discard
                </Button>
                <Button
                  variant="secondary"
                  disabled={locked || (!character.pendingBase && !character.acceptedBase)}
                  onClick={() =>
                    run("Re-pixelizing source", async () => {
                      const result = await api.reprocessPending(character.id);
                      if (result) applyResult(result);
                    }, { generating: true })
                  }
                >
                  Re-pixelize
                </Button>
                <Button variant="secondary" disabled={locked || !character.acceptedBase} onClick={() => run("Generating variation", async () => {
                  const result = await api.generateVariation(character.id);
                  if (result) applyResult(result);
                })}>
                  Variation
                </Button>
              </>
            }
          />
          <SpritePreviewCard
            title="Accepted Base"
            empty="No accepted base"
            asset={character.acceptedBase?.sprite}
            actions={
              <>
                <Button variant="secondary" disabled={locked || !character.pendingBase} onClick={() => run("Replacing base", () => api.replaceBase(character.id).then(setCharacter), { generating: false })}>
                  Replace base
                </Button>
                <Button variant="ghost" disabled={locked || !character.acceptedBase} onClick={() => run("Clearing reference", () => api.clearReference(character.id).then(setCharacter), { generating: false })}>
                  Clear reference
                </Button>
              </>
            }
          />
        </div>

        {generating && progress?.total ? (
          <p className="job-line">
            {progress.label}: {progress.currentItem || progress.step} · {progress.current}/{progress.total}
          </p>
        ) : null}

        <section className="block">
          <header className="block-head">
            <h2>{state ? `${state.name} directions` : "Directions"}</h2>
            <Button disabled={locked || !character.acceptedBase || !state} onClick={generateEight}>
              Generate 8 Directions
            </Button>
          </header>
          <p className="hint">
            Center is the accepted identity reference. Each facing is stored separately so you can accept, reject,
            regenerate, or lock one direction without losing the others. Order: {EXPORT_DIRECTION_ORDER.join(" → ")}.
          </p>
          <div className="compass studio-compass">
            {GRID.map((cell, index) => {
              if (cell === "REF") {
                return (
                  <div key="ref" className="compass-core ref-cell">
                    <span>REF</span>
                    <PixelImage asset={character.acceptedBase?.sprite} empty="No base" size={character.spriteSize} scale={3} />
                  </div>
                );
              }
              const slot = state?.directions.find((item) => item.direction === cell);
              const status = slotStatus(slot);
              const selected = selectedDirection === cell;
              return (
                <button
                  key={cell}
                  type="button"
                  className={`compass-cell ${selected ? "active" : ""} status-${status}`}
                  onClick={() => setSelectedDirection(cell)}
                >
                  <span>
                    {cell} · {status}
                  </span>
                  <PixelImage asset={slot?.frames[0]} empty="missing" size={character.spriteSize} scale={3} />
                </button>
              );
            })}
          </div>
        </section>

        <section className="block">
          <header className="block-head">
            <h2>States</h2>
            <Button variant="secondary" disabled={locked} onClick={() => setSection("identity")}>
              Edit identity
            </Button>
          </header>
          <div className="card-grid">
            {character.states.map((item) => {
              const preview = item.directions.find((slot) => slot.frames[0])?.frames[0];
              return (
                <article key={item.id} className={`state-card ${state?.id === item.id ? "active" : ""}`}>
                  <PixelImage asset={preview} empty="No frames" size={character.spriteSize} scale={3} />
                  <strong>{item.name}</strong>
                  <p>
                    {item.selectedDirections.length} dirs · {item.frameCount} frames · {item.kind}
                  </p>
                  <div className="chip-row">
                    <Button variant="secondary" onClick={() => setSelectedStateId(item.id)}>
                      Open
                    </Button>
                    <Button
                      disabled={locked || !character.acceptedBase}
                      onClick={() =>
                        run(`Generating ${item.name}`, async () => {
                          const result = await api.generateState(character.id, item.id);
                          if (result) applyResult(result);
                        })
                      }
                    >
                      Generate
                    </Button>
                  </div>
                </article>
              );
            })}
            {templates.slice(0, 6).map((template) =>
              character.states.some((item) => item.baseType === template.id) ? null : (
                <article key={template.id} className="state-card">
                  <strong>+ {template.name}</strong>
                  <p>{template.prompt}</p>
                  <Button
                    variant="ghost"
                    disabled={locked}
                    onClick={() =>
                      run("Adding state", () =>
                        api.addState(character.id, { name: template.name, templateId: template.id, baseType: template.id }).then(setCharacter),
                        { generating: false },
                      )
                    }
                  >
                    Add state
                  </Button>
                </article>
              ),
            )}
          </div>
        </section>
      </div>

      <aside className="studio-side">
        <section className="block">
          <header className="block-head">
            <h2>{selectedDirection}</h2>
          </header>
          {!state || !selectedSlot ? (
            <p className="hint">Select a state and direction.</p>
          ) : (
            <>
              <PixelImage asset={selectedSlot.frames[0]} empty="No sprite" size={character.spriteSize} scale={6} />
              <p className="hint">
                Status: <strong>{slotStatus(selectedSlot)}</strong>
                {selectedSlot.seed != null ? ` · seed ${selectedSlot.seed}` : ""}
              </p>
              <div className="chip-row">
                <Button
                  disabled={locked || !selectedSlot.frames[0]}
                  onClick={() => run("Accepting direction", () => api.acceptDirection(character.id, state.id, selectedDirection).then(setCharacter), { generating: false })}
                >
                  Accept
                </Button>
                <Button
                  variant="danger"
                  disabled={locked || !selectedSlot.frames[0]}
                  onClick={() =>
                    run("Rejecting direction", () => api.rejectDirection(character.id, state.id, selectedDirection, "wrong_direction").then(setCharacter), { generating: false })
                  }
                >
                  Reject
                </Button>
                <Button
                  variant="secondary"
                  disabled={locked || !character.acceptedBase || selectedSlot.locked}
                  onClick={() =>
                    run(`Regenerating ${selectedDirection}`, async () => {
                      const result = await api.generateDirection(character.id, { stateId: state.id, direction: selectedDirection });
                      if (result) applyResult(result);
                    })
                  }
                >
                  Regenerate
                </Button>
                <Button
                  variant="ghost"
                  disabled={locked || !selectedSlot.frames[0]}
                  onClick={() =>
                    run(selectedSlot.locked ? "Unlocking" : "Locking", () =>
                      (selectedSlot.locked ? api.unlockDirection : api.lockDirection)(character.id, state.id, selectedDirection).then(setCharacter),
                      { generating: false },
                    )
                  }
                >
                  {selectedSlot.locked ? "Unlock" : "Lock"}
                </Button>
                <Button
                  variant="secondary"
                  disabled={locked || !selectedSlot.frames[0]}
                  onClick={() =>
                    run("Refining from this sprite", async () => {
                      const result = await api.refine(character.id, { stateId: state.id, direction: selectedDirection, useAsReference: true });
                      if (result) applyResult(result);
                    })
                  }
                >
                  Use as reference
                </Button>
              </div>
              <label className="field">
                <span>Reject reason</span>
                <Select
                  defaultValue="wrong_direction"
                  onChange={(event) => {
                    const reason = event.target.value as RejectionReason;
                    if (!selectedSlot.frames[0]) return;
                    run("Rejecting direction", () => api.rejectDirection(character.id, state.id, selectedDirection, reason).then(setCharacter), { generating: false });
                  }}
                >
                  {REJECTION_REASONS.map((reason) => (
                    <option key={reason} value={reason}>
                      {reason.replaceAll("_", " ")}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="field">
                <span>Animation frames</span>
                <Select
                  value={state.frameCount}
                  onChange={(event) =>
                    run("Saving frames", () =>
                      api.updateState(character.id, state.id, { frameCount: Number(event.target.value) }).then(setCharacter),
                      { generating: false },
                    )
                  }
                >
                  {FRAME_COUNTS.map((count) => (
                    <option key={count} value={count}>
                      {count}
                    </option>
                  ))}
                </Select>
              </label>
              <Button
                disabled={locked || !character.acceptedBase}
                onClick={() =>
                  run("Generating animation", async () =>
                    api.generateAnimation(character.id, {
                      stateId: state.id,
                      direction: selectedDirection,
                      frameCount: state.frameCount,
                      action: state.customPrompt || state.name,
                    }),
                  )
                }
              >
                Animate this direction
              </Button>
              {selectedSlot.frames.length > 1 ? (
                <div className="frame-strip">
                  {selectedSlot.frames.map((frame, index) => (
                    <PixelImage key={frame.id} asset={frame} size={character.spriteSize} scale={2} empty={`F${index}`} />
                  ))}
                </div>
              ) : null}
            </>
          )}
        </section>
      </aside>
    </div>
  );
}
