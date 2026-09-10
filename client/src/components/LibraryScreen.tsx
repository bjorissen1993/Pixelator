import { useEffect, useState } from "react";
import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Button, Section, TextInput } from "./ui";
import type { MemoryEntry, MemorySuggestions, StyleProfile } from "@shared";

export function LibraryScreen() {
  const { character, run, setCharacter } = useWorkspace();
  const [styles, setStyles] = useState<StyleProfile[]>([]);
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [suggestions, setSuggestions] = useState<MemorySuggestions | null>(null);
  const [name, setName] = useState("New style");

  const reload = () => {
    api.styles().then(setStyles).catch(() => undefined);
    api.memory(character?.id).then(setEntries).catch(() => undefined);
    api.memorySuggestions(character?.id).then(setSuggestions).catch(() => undefined);
  };

  useEffect(() => {
    reload();
  }, [character?.id]);

  return (
    <div className="stack">
      <Section title="Style profiles">
        <p className="hint">
          Style profiles store palette, camera, outline, shading and prompt defaults. They are not the same as a
          character identity reference.
        </p>
        <div className="chip-row">
          <TextInput value={name} onChange={(event) => setName(event.target.value)} />
          <Button
            variant="secondary"
            onClick={() =>
              run("Creating style", async () => {
                await api.createStyle(name);
                reload();
              }, { generating: false })
            }
          >
            Create style
          </Button>
        </div>
        <div className="card-grid">
          {styles.map((profile) => (
            <article key={profile.id} className="state-card">
              <strong>{profile.name}</strong>
              <p>
                {profile.camera} · {profile.outline} · {profile.shading} · {profile.spriteSize}px
              </p>
              <Button
                disabled={!character}
                onClick={() =>
                  character &&
                  run("Applying style", () => api.applyStyle(character.id, profile.id).then(setCharacter), { generating: false })
                }
              >
                Inherit style
              </Button>
            </article>
          ))}
        </div>
      </Section>
      <Section title="Learning memory">
        <p className="hint">
          {suggestions?.notes.join(" ")} This stores accepted and rejected generations so Pixelator can suggest
          defaults. The image model itself is not being trained.
        </p>
        {suggestions?.recommendedSeeds.length ? (
          <p className="hint">Successful seeds: {suggestions.recommendedSeeds.join(", ")}</p>
        ) : null}
        {suggestions?.promptFragments.length ? (
          <p className="hint">Reuse fragments: {suggestions.promptFragments.join(" · ")}</p>
        ) : null}
        <div className="card-grid">
          {entries.slice(0, 12).map((entry) => (
            <article key={entry.id} className="state-card">
              <strong>
                {entry.kind} · {entry.direction || "base"}
              </strong>
              <p>
                {entry.characterName} · seed {entry.seed ?? "—"} · {entry.rejectionReason || "accepted"}
              </p>
            </article>
          ))}
        </div>
      </Section>
    </div>
  );
}
