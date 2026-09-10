import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button, Section } from "./ui";

export function GenerationPanel() {
  const { character, selectedStateId, selectedDirection, provider, prompt, usedReference, busy, run, applyResult } =
    useWorkspace();
  if (!character) return null;
  const state = character.states.find((item) => item.id === selectedStateId);

  const go = (label: string, fn: () => Promise<unknown>) =>
    run(label, async () => {
      const result = await fn();
      if (result && typeof result === "object" && result !== null && "character" in result) {
        applyResult(result as Awaited<ReturnType<typeof api.generateBase>>);
      }
    });

  return (
    <div className="stack">
      <Section title="Generation">
        <p className="hint">
          Provider: <strong>{provider?.name ?? "unknown"}</strong> · model {provider?.modelId}. Native pixel output:{" "}
          {provider?.nativePixelOutput ? "yes" : "no, 512px + pixel pipeline"}. Reference img2img:{" "}
          {provider?.supportsReference ? "available" : "not loaded"}.
        </p>
        <div className="action-grid">
          <Button disabled={!!busy} onClick={() => go("Generating base", () => api.generateBase(character.id))}>
            Generate base
          </Button>
          <Button
            disabled={!!busy || !state}
            variant="secondary"
            onClick={() => state && go(`Generating ${state.name}`, () => api.generateState(character.id, state.id))}
          >
            Generate selected state
          </Button>
          <Button
            disabled={!!busy || !state}
            variant="secondary"
            onClick={() => state && go("Generating missing directions", () => api.generateMissing(character.id, state.id))}
          >
            Generate missing directions
          </Button>
          <Button
            disabled={!!busy || !state}
            variant="secondary"
            onClick={() =>
              state &&
              go(`Regenerating ${selectedDirection}`, () =>
                api.generateDirection(character.id, { stateId: state.id, direction: selectedDirection }),
              )
            }
          >
            Regenerate current direction
          </Button>
          <Button
            disabled={!!busy}
            variant="secondary"
            onClick={() => go("Regenerating all states", () => api.generateAllStates(character.id))}
          >
            Regenerate all states
          </Button>
          <Button
            disabled={!!busy || !state}
            variant="secondary"
            onClick={() =>
              state &&
              go("Generating head variants", () => api.generateHeadVariants(character.id, state.id, selectedDirection))
            }
          >
            Generate head variants
          </Button>
        </div>
        {usedReference && <p className="hint">Last job used the accepted base as an img2img reference.</p>}
      </Section>
      {prompt && (
        <Section title="Composed prompt">
          <dl className="prompt-layers">
            {Object.entries(prompt).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value || "—"}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}
    </div>
  );
}
