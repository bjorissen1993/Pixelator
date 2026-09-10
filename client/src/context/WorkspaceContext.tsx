import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { DIRECTIONS_8 } from "@shared";
import type {
  CharacterProfile,
  Direction,
  GenerationProgress,
  GenerationResult,
  PromptLayers,
  ProviderInfo,
  StateTemplate,
  WorkspaceSection,
} from "@shared";
import { api } from "../api";

export const SECTIONS: WorkspaceSection[] = [
  { id: "character", label: "Character" },
  { id: "states", label: "States" },
  { id: "directions", label: "Directions" },
  { id: "emotion", label: "Emotion Profile" },
  { id: "head", label: "Head" },
  { id: "generation", label: "Generation" },
  { id: "export", label: "Export" },
];

const GENERATING_PATTERN = /generat|regen/i;

type RunOptions = { generating?: boolean };

type WorkspaceValue = {
  characters: CharacterProfile[];
  character: CharacterProfile | null;
  templates: StateTemplate[];
  provider: ProviderInfo | null;
  section: WorkspaceSection["id"];
  selectedStateId: string | null;
  selectedDirection: Direction;
  busy: string;
  generating: boolean;
  progress: GenerationProgress | null;
  error: string;
  prompt: PromptLayers | null;
  usedReference: boolean;
  setSection: (id: WorkspaceSection["id"]) => void;
  setSelectedStateId: (id: string | null) => void;
  setSelectedDirection: (direction: Direction) => void;
  refresh: () => Promise<void>;
  selectCharacter: (id: string) => void;
  setCharacter: (character: CharacterProfile) => void;
  run: <T>(label: string, fn: () => Promise<T>, options?: RunOptions) => Promise<T | undefined>;
  applyResult: (result: GenerationResult | CharacterProfile) => void;
};

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

function isGenerationResult(value: GenerationResult | CharacterProfile): value is GenerationResult {
  return "character" in value && "prompt" in value;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [characters, setCharacters] = useState<CharacterProfile[]>([]);
  const [character, setCharacter] = useState<CharacterProfile | null>(null);
  const [templates, setTemplates] = useState<StateTemplate[]>([]);
  const [provider, setProvider] = useState<ProviderInfo | null>(null);
  const [section, setSection] = useState<WorkspaceSection["id"]>("character");
  const [selectedStateId, setSelectedStateId] = useState<string | null>(null);
  const [selectedDirection, setSelectedDirection] = useState<Direction>("S");
  const [busy, setBusy] = useState("");
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<GenerationProgress | null>(null);
  const [error, setError] = useState("");
  const [prompt, setPrompt] = useState<PromptLayers | null>(null);
  const [usedReference, setUsedReference] = useState(false);
  const characterIdRef = useRef<string | null>(null);
  characterIdRef.current = character?.id ?? null;

  const applyCharacter = useCallback((next: CharacterProfile) => {
    setCharacter(next);
    setCharacters((current) => current.map((item) => (item.id === next.id ? next : item)));
    if (!selectedStateId && next.states[0]) setSelectedStateId(next.states[0].id);
  }, [selectedStateId]);

  const applyResult = useCallback((result: GenerationResult | CharacterProfile) => {
    if (isGenerationResult(result)) {
      applyCharacter(result.character);
      setPrompt(result.prompt);
      setUsedReference(result.usedReference);
      return;
    }
    applyCharacter(result);
  }, [applyCharacter]);

  const refresh = useCallback(async () => {
    const [list, stateTemplates, providerInfo] = await Promise.all([
      api.listCharacters(),
      api.templates(),
      api.provider(),
    ]);
    setCharacters(list);
    setTemplates(stateTemplates);
    setProvider(providerInfo);
    setCharacter((current) => {
      const next = list.find((item) => item.id === current?.id) ?? list[0] ?? null;
      if (next) {
        setSelectedStateId((currentId) => currentId ?? next.states[0]?.id ?? null);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  const run = useCallback(async <T,>(label: string, fn: () => Promise<T>, options?: RunOptions) => {
    const track = options?.generating ?? GENERATING_PATTERN.test(label);
    setBusy(label);
    setGenerating(track);
    setError("");
    if (track) {
      setProgress({
        active: true,
        label,
        step: "generating source image",
        steps: [
          "generating source image",
          "removing background",
          "cropping sprite",
          "reducing palette",
          "saving preview",
        ],
        stepIndex: 0,
      });
    }
    let timer: number | undefined;
    if (track && characterIdRef.current) {
      const id = characterIdRef.current;
      timer = window.setInterval(() => {
        api
          .generationProgress(id)
          .then((next) => {
            if (next.active || next.step) setProgress({ ...next, label: next.label || label });
          })
          .catch(() => undefined);
      }, 350);
    }
    try {
      return await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return undefined;
    } finally {
      if (timer) window.clearInterval(timer);
      setBusy("");
      setGenerating(false);
      setProgress(null);
    }
  }, []);

  const value = useMemo<WorkspaceValue>(
    () => ({
      characters,
      character,
      templates,
      provider,
      section,
      selectedStateId,
      selectedDirection: DIRECTIONS_8.includes(selectedDirection) ? selectedDirection : "S",
      busy,
      generating,
      progress,
      error,
      prompt,
      usedReference,
      setSection,
      setSelectedStateId,
      setSelectedDirection,
      refresh,
      selectCharacter: (id: string) => {
        const next = characters.find((item) => item.id === id);
        if (next) {
          setCharacter(next);
          setSelectedStateId(next.states[0]?.id ?? null);
        }
      },
      setCharacter: applyCharacter,
      run,
      applyResult,
    }),
    [
      applyCharacter,
      applyResult,
      busy,
      character,
      characters,
      error,
      generating,
      progress,
      prompt,
      provider,
      refresh,
      run,
      section,
      selectedDirection,
      selectedStateId,
      templates,
      usedReference,
    ],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("WorkspaceProvider missing");
  return value;
}
