import type { CanonicalBaseSession, CharacterProfile, Direction, GenerationProgress, GenerationResult, MemoryEntry, MemorySuggestions, ProviderInfo, StateTemplate, StyleProfile, GenerationJob, ApiErrorPayload } from "@shared";

export class ApiRequestError extends Error {
  details: string;
  traceId: string;
  context: Record<string, string>;

  constructor(payload: ApiErrorPayload) {
    super(payload.message || "Request failed");
    this.name = "ApiRequestError";
    this.details = payload.details || "";
    this.traceId = payload.traceId || "";
    this.context = payload.context || {};
  }
}

function asPayload(data: unknown, fallback: string): ApiErrorPayload {
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    if (record.error && typeof record.message === "string") {
      return {
        error: true,
        message: record.message,
        details: typeof record.details === "string" ? record.details : JSON.stringify(record.details ?? ""),
        traceId: typeof record.traceId === "string" ? record.traceId : "",
        context: (record.context as Record<string, string>) || {},
      };
    }
    const detail = record.detail;
    if (typeof detail === "string") {
      return { error: true, message: detail, details: detail };
    }
    if (detail && typeof detail === "object") {
      const nested = detail as Record<string, unknown>;
      if (typeof nested.message === "string") {
        return {
          error: true,
          message: nested.message,
          details: typeof nested.details === "string" ? nested.details : JSON.stringify(nested),
          traceId: typeof nested.traceId === "string" ? nested.traceId : "",
          context: (nested.context as Record<string, string>) || {},
        };
      }
      if (Array.isArray(detail)) {
        return {
          error: true,
          message: detail.map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : JSON.stringify(item))).join("; "),
          details: JSON.stringify(detail),
        };
      }
    }
  }
  return { error: true, message: fallback, details: fallback };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiRequestError(asPayload(data, response.statusText || "Request failed"));
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json() as Promise<T>;
  return undefined as T;
}

export async function downloadPost(path: string, filename: string, body?: unknown) {
  const response = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiRequestError(asPayload(data, "Download failed"));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export const api = {
  health: () => request<{ ok: boolean; provider: ProviderInfo }>("/health"),
  provider: () => request<ProviderInfo>("/api/providers"),
  templates: () => request<StateTemplate[]>("/api/templates/states"),
  listCharacters: () => request<CharacterProfile[]>("/api/characters"),
  getCharacter: (id: string) => request<CharacterProfile>(`/api/characters/${id}`),
  createCharacter: (body: { name: string; masterPrompt?: string }) =>
    request<CharacterProfile>("/api/characters", { method: "POST", body: JSON.stringify(body) }),
  patchCharacter: (id: string, body: Record<string, unknown>) =>
    request<CharacterProfile>(`/api/characters/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteCharacter: (id: string) => request<{ ok: boolean }>(`/api/characters/${id}`, { method: "DELETE" }),
  addState: (id: string, body: Record<string, unknown>) =>
    request<CharacterProfile>(`/api/characters/${id}/states`, { method: "POST", body: JSON.stringify(body) }),
  updateState: (id: string, stateId: string, body: Record<string, unknown>) =>
    request<CharacterProfile>(`/api/characters/${id}/states/${stateId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteState: (id: string, stateId: string) =>
    request<CharacterProfile>(`/api/characters/${id}/states/${stateId}`, { method: "DELETE" }),
  generateBase: (id: string, body: Record<string, unknown> = {}) =>
    request<GenerationResult>(`/api/characters/${id}/generate/base`, { method: "POST", body: JSON.stringify(body) }),
  acceptBase: (id: string) => request<CharacterProfile>(`/api/characters/${id}/accept-base`, { method: "POST", body: "{}" }),
  replaceBase: (id: string) => request<CharacterProfile>(`/api/characters/${id}/replace-base`, { method: "POST", body: "{}" }),
  clearReference: (id: string) => request<CharacterProfile>(`/api/characters/${id}/clear-reference`, { method: "POST", body: "{}" }),
  generateVariation: (id: string) =>
    request<GenerationResult>(`/api/characters/${id}/generate-variation`, { method: "POST", body: "{}" }),
  discardPending: (id: string) =>
    request<CharacterProfile>(`/api/characters/${id}/discard-pending`, { method: "POST", body: "{}" }),
  reprocessPending: (id: string) =>
    request<GenerationResult>(`/api/characters/${id}/reprocess-pending`, { method: "POST", body: "{}" }),
  generationProgress: (id: string) => request<GenerationProgress>(`/api/characters/${id}/generation-progress`),
  generateState: (id: string, stateId: string, body: Record<string, unknown> = {}) =>
    request<GenerationResult>(`/api/characters/${id}/generate/state/${stateId}`, { method: "POST", body: JSON.stringify(body) }),
  generateDirection: (id: string, body: { stateId: string; direction: Direction; frameIndex?: number; layer?: string }) =>
    request<GenerationResult>(`/api/characters/${id}/generate/direction`, { method: "POST", body: JSON.stringify(body) }),
  generateMissing: (id: string, stateId: string) =>
    request<GenerationResult>(`/api/characters/${id}/generate/missing-directions`, {
      method: "POST",
      body: JSON.stringify({ stateId, useReference: true }),
    }),
  generateAllStates: (id: string) =>
    request<GenerationResult>(`/api/characters/${id}/generate/all-states`, { method: "POST", body: "{}" }),
  generateHeadVariants: (id: string, stateId: string, direction: Direction) =>
    request<GenerationResult>(`/api/characters/${id}/generate/head-variants`, {
      method: "POST",
      body: JSON.stringify({ stateId, direction }),
    }),
  applyMasterPrompt: (id: string, body: Record<string, unknown>) =>
    request<GenerationResult>(`/api/characters/${id}/master-prompt`, { method: "POST", body: JSON.stringify(body) }),
  updateAnchors: (id: string, body: Record<string, unknown>) =>
    request<CharacterProfile>(`/api/characters/${id}/head-anchors`, { method: "POST", body: JSON.stringify(body) }),
  generateDirectionSet: (id: string, body: Record<string, unknown> = {}) =>
    request<{ job: GenerationJob; character: CharacterProfile }>(`/api/characters/${id}/generate/directions`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  acceptCandidate: (id: string, stateId: string, direction: Direction, assetId: string) =>
    request<CharacterProfile>(`/api/characters/${id}/directions/accept-candidate`, {
      method: "POST",
      body: JSON.stringify({ stateId, direction, assetId }),
    }),
  acceptDirection: (id: string, stateId: string, direction: Direction) =>
    request<CharacterProfile>(`/api/characters/${id}/directions/accept`, {
      method: "POST",
      body: JSON.stringify({ stateId, direction }),
    }),
  useAsReference: (id: string, stateId: string, direction: Direction) =>
    request<CharacterProfile>(`/api/characters/${id}/directions/use-as-reference`, {
      method: "POST",
      body: JSON.stringify({ stateId, direction }),
    }),
  rejectDirection: (id: string, stateId: string, direction: Direction, reason?: string, customReason?: string) =>
    request<CharacterProfile>(`/api/characters/${id}/directions/reject`, {
      method: "POST",
      body: JSON.stringify({ stateId, direction, reason, customReason }),
    }),
  lockDirection: (id: string, stateId: string, direction: Direction) =>
    request<CharacterProfile>(`/api/characters/${id}/directions/lock`, {
      method: "POST",
      body: JSON.stringify({ stateId, direction }),
    }),
  unlockDirection: (id: string, stateId: string, direction: Direction) =>
    request<CharacterProfile>(`/api/characters/${id}/directions/unlock`, {
      method: "POST",
      body: JSON.stringify({ stateId, direction }),
    }),
  removeDirection: (id: string, stateId: string, direction: Direction) =>
    request<CharacterProfile>(`/api/characters/${id}/states/${stateId}/directions/${direction}`, { method: "DELETE" }),
  generateAnimation: (id: string, body: Record<string, unknown>) =>
    request<{ job: GenerationJob; character: CharacterProfile }>(`/api/characters/${id}/generate/animation`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  refine: (id: string, body: Record<string, unknown>) =>
    request<GenerationResult>(`/api/characters/${id}/refine`, { method: "POST", body: JSON.stringify(body) }),
  getJob: (id: string) => request<{ job: GenerationJob; result: GenerationResult | null }>(`/api/jobs/${id}`),
  characterJobs: (id: string) => request<{ active: GenerationJob | null; jobs: GenerationJob[] }>(`/api/characters/${id}/jobs`),
  styles: () => request<StyleProfile[]>("/api/styles"),
  createStyle: (name: string) => request<StyleProfile>("/api/styles", { method: "POST", body: JSON.stringify({ name }) }),
  applyStyle: (id: string, styleId: string) =>
    request<CharacterProfile>(`/api/characters/${id}/apply-style/${styleId}`, { method: "POST" }),
  memory: (characterId?: string) =>
    request<MemoryEntry[]>(`/api/memory${characterId ? `?characterId=${characterId}` : ""}`),
  memorySuggestions: (characterId?: string) =>
    request<MemorySuggestions>(`/api/memory/suggestions${characterId ? `?characterId=${characterId}` : ""}`),
  canonicalBaseSession: () => request<CanonicalBaseSession>("/api/tests/berwynn-canonical"),
  generateCanonicalBase: (count = 4) =>
    request<CanonicalBaseSession>("/api/tests/berwynn-canonical/generate", {
      method: "POST",
      body: JSON.stringify({ count }),
    }),
  acceptCanonicalBase: (candidateId: string) =>
    request<CanonicalBaseSession>(`/api/tests/berwynn-canonical/accept/${candidateId}`, { method: "POST", body: "{}" }),
  rejectCanonicalBase: (candidateId: string) =>
    request<CanonicalBaseSession>(`/api/tests/berwynn-canonical/reject/${candidateId}`, { method: "POST", body: "{}" }),
};
