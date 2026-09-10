import { useState } from "react";
import type { CharacterState } from "@shared";
import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button, Field, PixelImage, Section, Select, TextInput, Toggle } from "./ui";

export function StatesScreen() {
  const { character, templates, selectedStateId, setSelectedStateId, setSection, run, setCharacter, applyResult, generating, busy } =
    useWorkspace();
  const [creating, setCreating] = useState(false);
  const [templateId, setTemplateId] = useState("idle");
  const [customName, setCustomName] = useState("");
  const [editing, setEditing] = useState<CharacterState | null>(null);
  if (!character) return null;

  const selected = character.states.find((state) => state.id === selectedStateId) ?? null;

  return (
    <div className="stack">
      <Section
        title="States"
        actions={<Button onClick={() => setCreating(true)}>+ New state</Button>}
      >
        <div className="card-grid">
          {character.states.map((state) => {
            const preview = state.directions.find((slot) => slot.frames[0])?.frames[0];
            return (
              <article key={state.id} className={`state-card ${selectedStateId === state.id ? "active" : ""}`}>
                <PixelImage asset={preview} cacheKey={preview?.createdAt} size={character.spriteSize} scale={4} />
                <div>
                  <strong>{state.name}</strong>
                  <p>
                    {state.selectedDirections.length} dirs · {state.kind} · {state.frameCount} frames
                  </p>
                </div>
                <div className="chip-row">
                  <Button variant="secondary" onClick={() => setSelectedStateId(state.id)}>
                    Select
                  </Button>
                  <Button variant="ghost" onClick={() => setEditing(state)}>
                    Edit
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      run(`Generating ${state.name}`, async () => {
                        const result = await api.generateState(character.id, state.id);
                        if (result) applyResult(result);
                      })
                    }
                    disabled={generating || !!busy}
                  >
                    Generate
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() =>
                      run("Deleting state", async () => {
                        const next = await api.deleteState(character.id, state.id);
                        setCharacter(next);
                      })
                    }
                  >
                    Delete
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      </Section>

      {creating && (
        <Section title="Add state" actions={<Button variant="ghost" onClick={() => setCreating(false)}>Close</Button>}>
          <div className="form-grid">
            <Field label="Template">
              <Select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
                <option value="custom">Custom</option>
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.category} / {template.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Custom name">
              <TextInput value={customName} onChange={(event) => setCustomName(event.target.value)} placeholder="Optional" />
            </Field>
          </div>
          <Button
            onClick={() =>
              run("Adding state", async () => {
                const body =
                  templateId === "custom"
                    ? { name: customName || "Custom", baseType: "custom", customPrompt: "", directionsMode: "8" }
                    : { name: customName, templateId, baseType: templateId };
                const next = await api.addState(character.id, body);
                setCharacter(next);
                setCreating(false);
                setCustomName("");
              })
            }
          >
            Add
          </Button>
        </Section>
      )}

      {editing && (
        <StateEditor
          state={editing}
          onClose={() => setEditing(null)}
          onSave={async (patch) => {
            await run("Saving state", async () => {
              const next = await api.updateState(character.id, editing.id, patch);
              setCharacter(next);
              setEditing(null);
            });
          }}
        />
      )}

      {selected && (
        <p className="hint">
          Selected state: <strong>{selected.name}</strong>. Open Directions to regenerate a facing, or{" "}
          <button className="link" onClick={() => setSection("studio")}>
            Studio
          </button>
          .
        </p>
      )}
    </div>
  );
}

function StateEditor({
  state,
  onClose,
  onSave,
}: {
  state: CharacterState;
  onClose: () => void;
  onSave: (patch: Record<string, unknown>) => void;
}) {
  const [draft, setDraft] = useState(state);
  return (
    <Section title={`Edit ${state.name}`} actions={<Button variant="ghost" onClick={onClose}>Close</Button>}>
      <div className="form-grid">
        <Field label="Name">
          <TextInput value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
        </Field>
        <Field label="Directions">
          <Select
            value={draft.directionsMode}
            onChange={(event) => setDraft({ ...draft, directionsMode: event.target.value as CharacterState["directionsMode"] })}
          >
            <option value="8">8 directions</option>
            <option value="4">4 directions</option>
            <option value="1">Single direction</option>
          </Select>
        </Field>
        <Field label="Frames">
          <TextInput
            type="number"
            min={1}
            max={16}
            value={draft.frameCount}
            onChange={(event) => setDraft({ ...draft, frameCount: Number(event.target.value), kind: Number(event.target.value) > 1 ? "animated" : "static" })}
          />
        </Field>
        <Field label="Animation speed">
          <TextInput
            type="number"
            value={draft.animationSpeed}
            onChange={(event) => setDraft({ ...draft, animationSpeed: Number(event.target.value) })}
          />
        </Field>
      </div>
      <Field label="Prompt override">
        <textarea rows={3} value={draft.customPrompt} onChange={(event) => setDraft({ ...draft, customPrompt: event.target.value })} />
      </Field>
      <div className="lock-grid">
        <Toggle label="Loop" checked={draft.loop} onChange={(loop) => setDraft({ ...draft, loop })} />
        <Toggle label="Separate head" checked={draft.headSeparated} onChange={(headSeparated) => setDraft({ ...draft, headSeparated })} />
        <Toggle label="Blinking metadata" checked={draft.blinkingEnabled} onChange={(blinkingEnabled) => setDraft({ ...draft, blinkingEnabled })} />
        <Toggle label="Look-at-target metadata" checked={draft.lookAtTargetEnabled} onChange={(lookAtTargetEnabled) => setDraft({ ...draft, lookAtTargetEnabled })} />
      </div>
      <Button
        onClick={() =>
          onSave({
            name: draft.name,
            customPrompt: draft.customPrompt,
            directionsMode: draft.directionsMode,
            frameCount: draft.frameCount,
            loop: draft.loop,
            animationSpeed: draft.animationSpeed,
            kind: draft.kind,
            headSeparated: draft.headSeparated,
            blinkingEnabled: draft.blinkingEnabled,
            lookAtTargetEnabled: draft.lookAtTargetEnabled,
          })
        }
      >
        Save state
      </Button>
    </Section>
  );
}
