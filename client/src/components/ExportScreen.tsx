import { downloadPost } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button, Section } from "./ui";

export function ExportScreen() {
  const { character, selectedStateId, selectedDirection, run } = useWorkspace();
  if (!character) return null;
  const slug = character.slug;

  const pull = (label: string, path: string, filename: string, body?: unknown) =>
    run(label, () => downloadPost(path, filename, body));

  return (
    <Section title="Phaser export">
        <p className="hint">
          Sprite sheets use direction order S, SW, W, NW, N, NE, E, SE. Training export writes accepted sprites and
          captions for future LoRA work — it does not train a model.
        </p>
      <div className="action-grid">
        <Button
          variant="secondary"
          onClick={() =>
            pull(
              "Exporting PNG",
              `/api/characters/${character.id}/export/png`,
              `${slug}-${selectedDirection}.png`,
              { stateId: selectedStateId, direction: selectedDirection },
            )
          }
        >
          Individual PNG
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            pull(
              "Exporting state sheet",
              `/api/characters/${character.id}/export/state-sheet`,
              `${slug}-state-sheet.png`,
              { stateId: selectedStateId },
            )
          }
        >
          State sprite sheet
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            pull(
              "Exporting character sheet",
              `/api/characters/${character.id}/export/character-sheet`,
              `${slug}-character-sheet.png`,
            )
          }
        >
          Complete character sheet
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            pull("Exporting metadata", `/api/characters/${character.id}/export/metadata`, `${slug}-metadata.json`)
          }
        >
          Metadata JSON
        </Button>
        <Button onClick={() => pull("Packaging ZIP", `/api/characters/${character.id}/export/zip`, `${slug}.zip`)}>
          ZIP character package
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            pull(
              "Exporting training set",
              `/api/characters/${character.id}/export/training-dataset`,
              `${slug}-training.zip`,
            )
          }
        >
          Training dataset (accepted only)
        </Button>
      </div>
    </Section>
  );
}
