import { useEffect, useState } from "react";
import { EXPORT_DIRECTION_ORDER, FRAME_COUNTS, REJECTION_REASONS, ROTATION_STRATEGIES } from "@shared";
import type { Direction, DirectionSlot, RejectionReason, SpriteAsset } from "@shared";
import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button, PixelImage, Select, SpritePreviewCard } from "./ui";
import { BaseCompositionPanel } from "./BaseCompositionPanel";
import { canAcceptAsBase, invalidBaseReasons } from "../baseValidation";

const GRID: Array<Direction | "REF"> = ["NW", "N", "NE", "W", "REF", "E", "SW", "S", "SE"];

function slotStatus(slot?: DirectionSlot) {
  if (!slot) return "missing";
  if (slot.locked) return "locked";
  if (slot.status && slot.status !== "missing") return slot.status;
  return slot.frames[0] ? "pending" : "missing";
}

function QualityBlock({ asset }: { asset?: SpriteAsset }) {
  const validation = asset?.validation;
  if (!validation) return null;
  return (
    <div className="quality-block">
      <p className="hint">
        Quality <strong>{validation.score ?? "—"}</strong>
        {validation.directionScore != null ? ` · facing ${validation.directionScore}` : ""}
        {validation.compositionScore != null ? ` · composition ${validation.compositionScore}` : ""}
        {validation.ok ? "" : " · not a good candidate"}
      </p>
      {validation.artifactWarning || validation.artifactDetected ? (
        <p className="hint warn-line">Possible duplicate figure / artifact</p>
      ) : null}
      {validation.silhouetteWarning ? <p className="hint warn-line">Silhouette warning</p> : null}
      {validation.spiritFormWarning ? <p className="hint warn-line">Spirit-form warning</p> : null}
      {validation.warnings.length ? (
        <ul className="quality-warnings">
          {validation.warnings.map((warning) => (
            <li key={warning.code}>
              {warning.message}
            </li>
          ))}
        </ul>
      ) : (
        <p className="hint">No quality warnings.</p>
      )}
    </div>
  );
}

function DebugBlock({ asset }: { asset?: SpriteAsset }) {
  const debug = asset?.debug;
  if (!debug) return null;
  return (
    <details className="debug-panel">
      <summary>Generation debug</summary>
      <dl>
        <div><dt>provider</dt><dd>{debug.provider || "—"}</dd></div>
        <div><dt>model</dt><dd>{debug.model || "—"}</dd></div>
        <div><dt>LoRA</dt><dd>{debug.loraLoaded ? debug.lora || "loaded" : "not loaded"}</dd></div>
        <div><dt>seed</dt><dd>{debug.seed ?? "—"}</dd></div>
        <div><dt>steps</dt><dd>{debug.steps ?? "—"}</dd></div>
        <div><dt>guidance</dt><dd>{debug.guidance ?? "—"}</dd></div>
        <div><dt>img2img strength</dt><dd>{debug.strength ?? "—"}</dd></div>
        <div><dt>reference</dt><dd>{debug.usedReference ? `${debug.referenceDirection || "base"} ${debug.referenceAssetId || ""}` : "none"}</dd></div>
        <div><dt>working / target</dt><dd>{debug.workingResolution ?? "—"} → {debug.targetResolution ?? "—"}</dd></div>
        <div><dt>palette</dt><dd>{debug.paletteMode || "—"}</dd></div>
        <div><dt>target direction</dt><dd>{debug.targetDirection || "—"}</dd></div>
        <div><dt>facing score</dt><dd>{debug.directionScore ?? "—"}</dd></div>
        <div><dt>artifact detection</dt><dd>{debug.artifactDetected ? "triggered" : "clear"}</dd></div>
        <div><dt>composition failed</dt><dd>{debug.compositionFailed ? "yes" : "no"}</dd></div>
        <div><dt>crop retries</dt><dd>{debug.cropRetries ?? 0}</dd></div>
        <div><dt>prompt</dt><dd>{debug.prompt || "—"}</dd></div>
        <div><dt>negative</dt><dd>{debug.negativePrompt || "—"}</dd></div>
      </dl>
    </details>
  );
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
  const [rejectReason, setRejectReason] = useState<RejectionReason>("wrong_direction");
  const [refineStrength, setRefineStrength] = useState(0.35);
  const [rotationStrategy, setRotationStrategy] = useState<"stable" | "incremental">(
    character?.rotationStrategy === "incremental" ? "incremental" : "stable",
  );
  useEffect(() => {
    setRotationStrategy(character?.rotationStrategy === "incremental" ? "incremental" : "stable");
  }, [character?.id, character?.rotationStrategy]);
  if (!character) return null;
  const state = character.states.find((item) => item.id === selectedStateId) ?? character.states[0];
  const locked = generating || !!busy;
  const selectedSlot = state?.directions.find((item) => item.direction === selectedDirection);
  const pendingInvalid = invalidBaseReasons(character.pendingBase?.validation);
  const acceptDisabled = locked || !canAcceptAsBase(character.pendingBase);
  const acceptedInvalid = invalidBaseReasons(character.acceptedBase?.sprite?.validation);
  const southSlot = state?.directions.find((item) => item.direction === "S");
  const refAsset = character.acceptedBase?.sprite ?? character.pendingBase ?? southSlot?.frames[0];

  const generateEight = () => {
    if (!state) return;
    run("Generate All Directions", async () => {
      const started = await api.generateDirectionSet(character.id, {
        stateId: state.id,
        useReference: true,
        rotationStrategy,
      });
      return started;
    });
  };

  const removeDirection = (direction: Direction) => {
    if (!state) return;
    if (!window.confirm("Remove this direction? This will clear the sprite and set the slot back to missing.")) return;
    run("Removing direction", async () => {
      const next = await api.removeDirection(character.id, state.id, direction);
      setCharacter(next);
      const nextState = next.states.find((item) => item.id === state.id) ?? next.states[0];
      const slot = nextState?.directions.find((item) => item.direction === direction);
      if (!slot || slot.status === "missing" || !slot.frames[0]) {
        const fallback = (["S", ...EXPORT_DIRECTION_ORDER.filter((item) => item !== "S")] as Direction[]).find((item) => {
          const found = nextState?.directions.find((entry) => entry.direction === item);
          return Boolean(found?.frames[0] && item !== direction);
        });
        setSelectedDirection(fallback ?? "S");
      }
    }, { generating: false });
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
              {character.acceptedBase ? " · identity locked" : " · accept a valid South base before filling other facings"}
            </p>
          </div>
          <div className="chip-row">
            <Button disabled={locked} onClick={() => run("Generating south", async () => {
              const result = await api.generateBase(character.id, { seedMode: character.seedLocked ? "locked" : "random" });
              if (result) applyResult(result);
            })}>
              Generate
            </Button>
            <Button
              disabled={locked || !state}
              title={
                acceptedInvalid.length
                  ? "Accepted base is invalid and will not be used as a reference"
                  : character.acceptedBase
                    ? "Generate remaining directions from the accepted base"
                    : "Generate and validate South first, then the other facings if South is usable"
              }
              onClick={generateEight}
            >
              Generate All Directions
            </Button>
          </div>
        </section>

        <div className="ref-row">
          <SpritePreviewCard
            title={character.pendingBase?.fromDirection ? `Pending Sprite · ${character.pendingBase.fromDirection}` : "Pending Sprite"}
            empty="No pending South sprite"
            asset={character.pendingBase}
            loading={generating && !progress?.currentItem}
            progress={progress}
            actions={
              <>
                <Button disabled={acceptDisabled} onClick={() => run("Accepting base", () => api.acceptBase(character.id).then(setCharacter), { generating: false })}>
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
                <Button variant="secondary" disabled={acceptDisabled} onClick={() => run("Replacing base", () => api.replaceBase(character.id).then(setCharacter), { generating: false })}>
                  Replace base
                </Button>
                <Button variant="ghost" disabled={locked || !character.acceptedBase} onClick={() => run("Clearing reference", () => api.clearReference(character.id).then(setCharacter), { generating: false })}>
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
        ) : null}
        <BaseCompositionPanel asset={character.pendingBase} />
        {acceptedInvalid.length ? (
          <ul className="quality-warnings invalid-base">
            {acceptedInvalid.map((reason) => (
              <li key={`accepted-${reason}`}>{reason}</li>
            ))}
          </ul>
        ) : null}

        {generating && progress?.total ? (
          <p className="job-line">
            {progress.label}: {progress.currentItem || progress.step} · {progress.current}/{progress.total}
          </p>
        ) : null}

        <section className="block">
          <header className="block-head">
            <h2>{state ? `${state.name} directions` : "Directions"}</h2>
          </header>
            <p className="hint">
            Center is the selected direction preview. If the selected slot is empty, Accepted Base is shown there.
            Generate creates one South idle sprite. Generate All Directions rotates from that reference.
            Stable identity reuses South for every facing. Incremental rotation walks 45° and can accumulate error.
            Order: {EXPORT_DIRECTION_ORDER.join(" → ")}.
          </p>
          <label className="field">
            <span>Rotation strategy</span>
            <Select
              value={rotationStrategy}
              onChange={(event) => {
                const next = event.target.value as "stable" | "incremental";
                setRotationStrategy(next);
                run("Saving rotation strategy", () => api.patchCharacter(character.id, { rotationStrategy: next }).then(setCharacter), {
                  generating: false,
                });
              }}
            >
              {ROTATION_STRATEGIES.map((strategy) => (
                <option key={strategy} value={strategy}>
                  {strategy === "stable" ? "Stable identity (from South)" : "Incremental rotation (45° steps)"}
                </option>
              ))}
            </Select>
          </label>
          <div className="compass studio-compass">
            {GRID.map((cell) => {
              if (cell === "REF") {
                const selectedStatus = slotStatus(selectedSlot);
                const hasSelected = Boolean(selectedSlot?.frames[0]);
                const selectedAsset = selectedSlot?.frames[0] ?? character.acceptedBase?.sprite ?? (selectedDirection === "S" ? refAsset : undefined);
                const showingBase = !hasSelected && Boolean(character.acceptedBase?.sprite);
                return (
                  <div key="selected" className={`compass-core selected-preview status-${selectedStatus}`}>
                    <span className="selected-label">
                      {showingBase ? "Accepted Base" : `Selected · ${selectedDirection}`}
                      <span className={`status-badge status-${selectedStatus}`}>{showingBase ? "reference" : selectedStatus}</span>
                    </span>
                    <PixelImage
                      asset={selectedAsset}
                      empty={`No ${selectedDirection} sprite`}
                      size={character.spriteSize}
                      scale={7}
                    />
                  </div>
                );
              }
              const slot = state?.directions.find((item) => item.direction === cell);
              const status = slotStatus(slot);
              const selected = selectedDirection === cell;
              const invalid = status === "rejected" || slot?.frames[0]?.validation?.ok === false;
              return (
                <div key={cell} className={`compass-cell ${selected ? "active" : ""} status-${status}`}>
                  <button type="button" className="compass-select" onClick={() => setSelectedDirection(cell)}>
                    <span className="dir-meta">
                      <span className="dir-name">{cell}</span>
                      <span className={`status-badge status-${status}`}>{status}</span>
                      {invalid ? <span className="warn-dot" title="Bad candidate">!</span> : null}
                    </span>
                    <PixelImage asset={slot?.frames[0]} empty="missing" size={character.spriteSize} scale={2} />
                  </button>
                  {status !== "missing" && status !== "locked" ? (
                    <button
                      type="button"
                      className="btn remove compass-remove"
                      disabled={locked}
                      onClick={() => removeDirection(cell)}
                    >
                      Remove
                    </button>
                  ) : null}
                </div>
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
                {selectedSlot.frames[0]?.referenceDirection ? ` · ref ${selectedSlot.frames[0].referenceDirection}` : ""}
              </p>
              <QualityBlock asset={selectedSlot.frames[0]} />
              {selectedSlot.candidates && selectedSlot.candidates.length > 0 ? (
                <div>
                  <p className="hint">Candidates — accept one. Accepted directions are not overwritten until you pick.</p>
                  <div className="frame-strip">
                    {selectedSlot.candidates.map((asset, index) => (
                      <button
                        key={asset.id}
                        type="button"
                        className={`candidate-btn ${selectedSlot.frames[0]?.id === asset.id ? "active" : ""}`}
                        disabled={locked || selectedSlot.locked}
                        onClick={() =>
                          run("Accepting candidate", () => api.acceptCandidate(character.id, state.id, selectedDirection, asset.id).then(setCharacter), {
                            generating: false,
                          })
                        }
                      >
                        <PixelImage asset={asset} size={character.spriteSize} scale={2} empty={`C${index + 1}`} />
                        <span>{asset.validation?.score ?? "—"}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
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
                    run("Rejecting direction", () => api.rejectDirection(character.id, state.id, selectedDirection, rejectReason).then(setCharacter), { generating: false })
                  }
                >
                  Reject
                </Button>
                <Button
                  variant="secondary"
                  disabled={locked || selectedSlot.locked}
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
                    run("Using as reference", () => api.useAsReference(character.id, state.id, selectedDirection).then(setCharacter), {
                      generating: false,
                    })
                  }
                >
                  Use as Reference
                </Button>
                <Button
                  variant="secondary"
                  disabled={locked || !selectedSlot.frames[0]}
                  onClick={() =>
                    run("Refining from this sprite", async () => {
                      const result = await api.refine(character.id, {
                        stateId: state.id,
                        direction: selectedDirection,
                        useAsReference: true,
                        strength: refineStrength,
                      });
                      if (result) applyResult(result);
                    })
                  }
                >
                  Refine
                </Button>
                <Button
                  variant="remove"
                  disabled={locked || selectedSlot.locked || slotStatus(selectedSlot) === "missing"}
                  onClick={() => removeDirection(selectedDirection)}
                >
                  Remove
                </Button>
              </div>
              <label className="field">
                <span>Init strength {refineStrength.toFixed(2)}</span>
                <input
                  type="range"
                  min={0.08}
                  max={0.85}
                  step={0.01}
                  value={refineStrength}
                  onChange={(event) => setRefineStrength(Number(event.target.value))}
                />
              </label>
              <label className="field">
                <span>Reject reason</span>
                <Select
                  value={rejectReason}
                  onChange={(event) => setRejectReason(event.target.value as RejectionReason)}
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
              <DebugBlock asset={selectedSlot.frames[0] || selectedSlot.candidates?.[0]} />
            </>
          )}
        </section>
      </aside>
    </div>
  );
}
