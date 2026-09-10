import type { Direction } from "@shared";
import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button, PixelImage, Section } from "./ui";

const GRID: Array<Direction | null> = ["NW", "N", "NE", "W", null, "E", "SW", "S", "SE"];

export function DirectionsScreen() {
  const {
    character,
    selectedStateId,
    selectedDirection,
    setSelectedDirection,
    run,
    applyResult,
    busy,
  } = useWorkspace();
  if (!character) return null;
  const state = character.states.find((item) => item.id === selectedStateId);
  if (!state) return <p className="hint">Select a state first.</p>;

  return (
    <Section
      title={`${state.name} directions`}
      actions={
        <div className="chip-row">
          <Button
            variant="secondary"
            onClick={() =>
              run("Generating missing directions", async () => {
                const result = await api.generateMissing(character.id, state.id);
                if (result) applyResult(result);
              })
            }
          >
            Generate missing
          </Button>
        </div>
      }
    >
      <div className="compass">
        {GRID.map((direction, index) => {
          if (!direction) return <div key={index} className="compass-core">{state.name}</div>;
          const slot = state.directions.find((item) => item.direction === direction);
          const selected = selectedDirection === direction;
          const enabled = state.selectedDirections.includes(direction);
          const frame = slot?.frames[0];
          return (
            <div key={direction} className={`compass-cell ${selected ? "active" : ""} ${enabled ? "" : "dim"}`}>
              <button type="button" className="compass-select" onClick={() => setSelectedDirection(direction)}>
                <span>{direction}</span>
                <PixelImage path={frame?.path} cacheKey={frame?.createdAt} size={character.spriteSize} scale={3} />
              </button>
              <Button
                variant="ghost"
                disabled={!enabled || !!busy}
                onClick={() =>
                  run(`Regenerating ${direction}`, async () => {
                    const result = await api.generateDirection(character.id, {
                      stateId: state.id,
                      direction,
                    });
                    if (result) applyResult(result);
                  })
                }
              >
                Regen
              </Button>
            </div>
          );
        })}
      </div>
      <p className="hint">
        Selected: <strong>{selectedDirection}</strong>. Each facing is stored separately and can be regenerated without
        touching the others. Enabled set: {state.selectedDirections.join(", ")}.
      </p>
    </Section>
  );
}
