import { useEffect, useState } from "react";
import type { EmotionProfile } from "@shared";
import { api } from "../api";
import { useWorkspace } from "../context/WorkspaceContext";
import { Area, Button, Field, Section, Select } from "./ui";

export function EmotionScreen() {
  const { character, run, setCharacter } = useWorkspace();
  const [draft, setDraft] = useState<EmotionProfile | null>(character?.emotion ?? null);
  useEffect(() => setDraft(character?.emotion ?? null), [character]);
  if (!character || !draft) return null;

  return (
    <Section
      title="Emotion profile"
      actions={
        <Button
          onClick={() => run("Saving emotion profile", () => api.patchCharacter(character.id, { emotion: draft }).then(setCharacter))}
        >
          Save emotion profile
        </Button>
      }
    >
      <p className="hint">
        States like laughing or talking inherit this profile. A restrained character will not get the same pose language as
        an expressive one.
      </p>
      <div className="form-grid">
        <Field label="Expressiveness">
          <Select value={draft.expressiveness} onChange={(event) => setDraft({ ...draft, expressiveness: event.target.value as EmotionProfile["expressiveness"] })}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </Select>
        </Field>
        <Field label="Body movement">
          <Select value={draft.bodyMovement} onChange={(event) => setDraft({ ...draft, bodyMovement: event.target.value as EmotionProfile["bodyMovement"] })}>
            <option value="subtle">Subtle</option>
            <option value="natural">Natural</option>
            <option value="animated">Animated</option>
          </Select>
        </Field>
        <Field label="Facial range">
          <Select value={draft.facialRange} onChange={(event) => setDraft({ ...draft, facialRange: event.target.value as EmotionProfile["facialRange"] })}>
            <option value="limited">Limited</option>
            <option value="balanced">Balanced</option>
            <option value="broad">Broad</option>
          </Select>
        </Field>
      </div>
      <Field label="Default mood">
        <Area rows={2} value={draft.defaultMood} onChange={(event) => setDraft({ ...draft, defaultMood: event.target.value })} />
      </Field>
      <div className="form-grid">
        <Field label="Laughter style">
          <Area rows={2} value={draft.laughterStyle} onChange={(event) => setDraft({ ...draft, laughterStyle: event.target.value })} />
        </Field>
        <Field label="Sadness style">
          <Area rows={2} value={draft.sadnessStyle} onChange={(event) => setDraft({ ...draft, sadnessStyle: event.target.value })} />
        </Field>
        <Field label="Anger style">
          <Area rows={2} value={draft.angerStyle} onChange={(event) => setDraft({ ...draft, angerStyle: event.target.value })} />
        </Field>
        <Field label="Talking style">
          <Area rows={2} value={draft.talkingStyle} onChange={(event) => setDraft({ ...draft, talkingStyle: event.target.value })} />
        </Field>
      </div>
      <Field label="Custom notes">
        <Area rows={3} value={draft.customEmotionNotes} onChange={(event) => setDraft({ ...draft, customEmotionNotes: event.target.value })} />
      </Field>
    </Section>
  );
}
