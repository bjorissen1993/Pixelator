import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button, PipelineSteps, Section } from "./ui";

export function GenerationPanel() {
  const { character, selectedStateId, selectedDirection, provider, prompt, usedReference, busy, generating, progress, run, applyResult } =
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
          Provider: <strong>{provider?.name ?? "unconfigured"}</strong> · model {provider?.modelId || "none"}
          {provider?.fallbackTurbo ? " (optional SDXL-Turbo fallback, not the default engine)" : ""}.
          Capabilities: textToSprite {provider?.capabilities?.textToSprite ? "yes" : "no"}, rotateSprite{" "}
          {provider?.capabilities?.rotateSprite ? "yes" : "no"}, generate8Directions{" "}
          {provider?.capabilities?.generate8Directions ? (provider.capabilities.batchIsSequential ? "sequential" : "native batch") : "no"}
          , paletteConditioning {provider?.capabilities?.paletteConditioning ? "yes" : "no"}, initImage{" "}
          {provider?.capabilities?.initImage ? "yes" : "no"}.
          Sprite sizes: {(provider?.capabilities?.preferredSizes ?? [32, 48, 64, 96, 128]).join(", ")}.
        </p>
        <div className="action-grid">
          <Button disabled={generating || !!busy} onClick={() => go("Generating base", () => api.generateBase(character.id))}>
            Generate base
          </Button>
          <Button
            disabled={generating || !!busy || !state}
            variant="secondary"
            onClick={() => state && go(`Generating ${state.name}`, () => api.generateState(character.id, state.id))}
          >
            Generate selected state
          </Button>
          <Button
            disabled={generating || !!busy || !state}
            variant="secondary"
            onClick={() => state && go("Generating missing directions", () => api.generateMissing(character.id, state.id))}
          >
            Generate missing directions
          </Button>
          <Button
            disabled={generating || !!busy || !state}
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
            disabled={generating || !!busy}
            variant="secondary"
            onClick={() => go("Regenerating all states", () => api.generateAllStates(character.id))}
          >
            Regenerate all states
          </Button>
          <Button
            disabled={generating || !!busy || !state}
            variant="secondary"
            onClick={() =>
              state &&
              go("Generating head variants", () => api.generateHeadVariants(character.id, state.id, selectedDirection))
            }
          >
            Generate head variants
          </Button>
        </div>
        {generating && (
          <div className="sprite-loading generation-inline" aria-live="polite">
            <span className="spinner" aria-hidden="true" />
            <div>
              <strong>{progress?.label || busy}</strong>
              <p>{progress?.step || "Generating sprite"}</p>
              <PipelineSteps progress={progress} />
            </div>
          </div>
        )}
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
