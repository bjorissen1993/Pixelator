import type { CharacterProfile, Direction, GenerationProgress, GenerationResult, MemoryEntry, MemorySuggestions, ProviderInfo, StateTemplate, StyleProfile, GenerationJob } from "@shared";

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : JSON.stringify(item))).join("; ");
  }
  return "Request failed";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(formatDetail((data as { detail?: unknown }).detail) || response.statusText);
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
    throw new Error(formatDetail((data as { detail?: unknown }).detail) || "Download failed");
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
  acceptDirection: (id: string, stateId: string, direction: Direction) =>
    request<CharacterProfile>(`/api/characters/${id}/directions/accept`, {
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
  generateAnimation: (id: string, body: Record<string, unknown>) =>
    request<{ job: GenerationJob; character: CharacterProfile }>(`/api/characters/${id}/generate/animation`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  refine: (id: string, body: Record<string, unknown>) =>
    request<GenerationResult>(`/api/characters/${id}/refine`, { method: "POST", body: JSON.stringify(body) }),
  getJob: (jobId: string) => request<{ job: GenerationJob; result: GenerationResult | null }>(`/api/jobs/${jobId}`),
  characterJobs: (id: string) => request<{ active: GenerationJob | null; jobs: GenerationJob[] }>(`/api/characters/${id}/jobs`),
  styles: () => request<StyleProfile[]>("/api/styles"),
  createStyle: (name: string) => request<StyleProfile>("/api/styles", { method: "POST", body: JSON.stringify({ name }) }),
  applyStyle: (id: string, styleId: string) =>
    request<CharacterProfile>(`/api/characters/${id}/apply-style/${styleId}`, { method: "POST" }),
  memory: (characterId?: string) =>
    request<MemoryEntry[]>(`/api/memory${characterId ? `?characterId=${characterId}` : ""}`),
  memorySuggestions: (characterId?: string) =>
    request<MemorySuggestions>(`/api/memory/suggestions${characterId ? `?characterId=${characterId}` : ""}`),
};
