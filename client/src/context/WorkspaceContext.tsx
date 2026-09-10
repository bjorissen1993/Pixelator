import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { DIRECTIONS_8 } from "@shared";
import type {
  ApiErrorPayload,
  CharacterProfile,
  Direction,
  GenerationProgress,
  GenerationResult,
  PromptLayers,
  ProviderInfo,
  StateTemplate,
  WorkspaceSection,
} from "@shared";
import { api, ApiRequestError } from "../api";

export { SECTIONS } from "../sections";

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
  error: ApiErrorPayload | null;
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

function jobIdFrom(value: unknown): string | undefined {
  if (!value || typeof value !== "object") return undefined;
  const job = (value as { job?: { id?: string } | null }).job;
  return job?.id;
}

async function waitForJob(
  jobId: string,
  label: string,
  setProgress: (updater: (current: GenerationProgress | null) => GenerationProgress | null) => void,
): Promise<GenerationResult | null> {
  for (;;) {
    const data = await api.getJob(jobId);
    const job = data.job;
    if (!job) {
      throw new ApiRequestError({
        error: true,
        message: "Generation job disappeared. The backend may have restarted.",
        details: jobId,
      });
    }
    setProgress((current) => ({
      active: job.status === "queued" || job.status === "generating" || job.status === "processing",
      label: job.label || label,
      step: job.currentItem || job.status,
      steps: current?.steps ?? ["queued", "Generating South", "Generating rotations", "Applying palette", "Saving assets"],
      stepIndex: current?.stepIndex ?? 0,
      current: job.current,
      total: job.total,
      currentItem: job.currentItem,
    }));
    if (job.status === "completed") {
      return data.result;
    }
    if (job.status === "failed") {
      throw new ApiRequestError({
        error: true,
        message: job.error || "Generation failed",
        details: job.errorDetails || job.error || "",
        traceId: job.traceId || "",
      });
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [characters, setCharacters] = useState<CharacterProfile[]>([]);
  const [character, setCharacter] = useState<CharacterProfile | null>(null);
  const [templates, setTemplates] = useState<StateTemplate[]>([]);
  const [provider, setProvider] = useState<ProviderInfo | null>(null);
  const [section, setSection] = useState<WorkspaceSection["id"]>("studio");
  const [selectedStateId, setSelectedStateId] = useState<string | null>(null);
  const [selectedDirection, setSelectedDirection] = useState<Direction>("S");
  const [busy, setBusy] = useState("");
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<GenerationProgress | null>(null);
  const [error, setError] = useState<ApiErrorPayload | null>(null);
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
    if (!result || typeof result !== "object") return;
    if (isGenerationResult(result)) {
      if (result.character) applyCharacter(result.character);
      if (result.prompt) setPrompt(result.prompt);
      setUsedReference(Boolean(result.usedReference));
      return;
    }
    if ("id" in result && "states" in result) applyCharacter(result);
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
    refresh().catch((err: unknown) => {
      if (err instanceof ApiRequestError) setError(err);
      else setError({ message: err instanceof Error ? err.message : String(err) });
    });
  }, [refresh]);

  const run = useCallback(async <T,>(label: string, fn: () => Promise<T>, options?: RunOptions) => {
    const track = options?.generating ?? GENERATING_PATTERN.test(label);
    setBusy(label);
    setGenerating(track);
    setError(null);
    if (track) {
      setProgress({
        active: true,
        label,
        step: "queued",
        steps: [
          "queued",
          "Generating South",
          "Generating rotations",
          "Applying palette",
          "Saving assets",
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
            if (next.active || next.step) setProgress((current) => ({ ...(current ?? next), ...next, label: next.label || label }));
          })
          .catch(() => undefined);
      }, 350);
    }
    try {
      const result = await fn();
      let jobId = jobIdFrom(result);
      if (!jobId && track && characterIdRef.current) {
        try {
          const listed = await api.characterJobs(characterIdRef.current);
          jobId = listed.active?.id;
        } catch {
          jobId = undefined;
        }
      }
      if (jobId) {
        const completed = await waitForJob(jobId, label, setProgress);
        if (completed) applyResult(completed);
        setError(null);
        return (completed as T) ?? result;
      }
      if (result && typeof result === "object") {
        applyResult(result as GenerationResult | CharacterProfile);
      }
      setError(null);
      return result;
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError({
          error: true,
          message: err.message,
          details: err.details,
          traceId: err.traceId,
          context: err.context,
        });
      } else {
        setError({ message: err instanceof Error ? err.message : String(err), details: err instanceof Error ? err.stack : String(err) });
      }
      return undefined;
    } finally {
      if (timer) window.clearInterval(timer);
      setBusy("");
      setGenerating(false);
      setProgress(null);
    }
  }, [applyResult]);

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
