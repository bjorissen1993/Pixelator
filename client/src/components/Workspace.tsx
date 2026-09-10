import { useState } from "react";
import { api } from "../api";
import { SECTIONS, useWorkspace } from "../context/WorkspaceContext";
import { GenerationStatus, Button, TextInput } from "./ui";
import { CharacterScreen } from "./CharacterScreen";
import { EmotionScreen } from "./EmotionScreen";
import { StudioScreen } from "./StudioScreen";
import { LibraryScreen } from "./LibraryScreen";
import { ExportScreen } from "./ExportScreen";

export function Workspace() {
  const {
    characters,
    character,
    section,
    setSection,
    selectCharacter,
    refresh,
    run,
    busy,
    generating,
    progress,
    error,
    provider,
  } = useWorkspace();
  const [newName, setNewName] = useState("");

  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="brand">
          <span className="eyebrow">{provider?.id === "pixellab" ? "PixelLab API" : "Local-first"}</span>
          <h1>Pixelator</h1>
          <p>Character System v2</p>
        </div>
        <label className="field">
          <span>Character</span>
          <select value={character?.id ?? ""} onChange={(event) => selectCharacter(event.target.value)}>
            {characters.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <div className="new-char">
          <TextInput placeholder="New character name" value={newName} onChange={(event) => setNewName(event.target.value)} />
          <Button
            variant="secondary"
            disabled={!!busy}
            onClick={() =>
              run("Creating character", async () => {
                if (!newName.trim()) return;
                const created = await api.createCharacter({ name: newName.trim() });
                setNewName("");
                await refresh();
                selectCharacter(created.id);
              })
            }
          >
            Create
          </Button>
        </div>
        <nav>
          {SECTIONS.map((item) => (
            <button
              key={item.id}
              className={section === item.id ? "nav-item active" : "nav-item"}
              onClick={() => setSection(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <p className="sidebar-note">{provider?.notes}</p>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <h2>{character?.name ?? "No character"}</h2>
            <p>
              Provider {provider?.name ?? "unconfigured"} · {provider?.modelId || "no model"}
              {provider?.id === "unconfigured"
                ? " · configure PIXELATOR_MODEL_ID or PIXELLAB_API_KEY"
                : provider?.fallbackTurbo
                  ? " · optional Turbo fallback"
                  : provider?.capabilities?.rotateSprite
                    ? " · reference-conditioned rotation"
                    : " · no rotateSprite"}
              {provider?.capabilities?.generate8Directions
                ? provider?.capabilities?.batchIsSequential
                  ? " · 8-dir sequential"
                  : " · 8-dir native batch"
                : ""}
              {provider?.loraLoaded ? " · LoRA loaded" : provider?.loraPath ? " · LoRA configured" : ""}
              {provider?.ipAdapterLoaded ? " · IP-Adapter" : ""}
              {` · sprite ${character?.spriteSize ?? 48}px`}
              {character?.acceptedBase ? ` · palette ${character.paletteMode}` : ""}
              {character?.rotationStrategy ? ` · ${character.rotationStrategy} rotation` : ""}
              {character?.acceptedBase ? " · base locked" : ""}
            </p>
          </div>
          <div className="badge">{character?.spriteSize ?? 48}×{character?.spriteSize ?? 48}</div>
        </header>
        <GenerationStatus error={error} busy={busy} generating={generating} progress={progress} />
        <div className="content">
          {section === "studio" && <StudioScreen />}
          {section === "identity" && (
            <>
              <CharacterScreen />
              <EmotionScreen />
            </>
          )}
          {section === "library" && <LibraryScreen />}
          {section === "export" && <ExportScreen />}
        </div>
      </main>
    </div>
  );
}
