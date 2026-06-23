import { getToken } from "./auth";
import type { Account, Run, RunResult, Site } from "./types";

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<any>("/health"),

  getAccount: () => req<Account>("/account"),
  setKeys: (keys: Record<string, string>) =>
    req<Account>("/account/keys", { method: "PUT", body: JSON.stringify(keys) }),

  listSites: () => req<Site[]>("/sites"),
  createSite: (site: Partial<Site>) =>
    req<Site>("/sites", { method: "POST", body: JSON.stringify(site) }),
  updateSite: (id: string, patch: Partial<Site>) =>
    req<Site>(`/sites/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteSite: (id: string) => req<void>(`/sites/${id}`, { method: "DELETE" }),

  listRuns: (siteId: string) => req<Run[]>(`/sites/${siteId}/runs`),
  createRun: (siteId: string, body: any) =>
    req<Run>(`/sites/${siteId}/runs`, { method: "POST", body: JSON.stringify(body) }),
  getRun: (siteId: string, runId: string) => req<Run>(`/sites/${siteId}/runs/${runId}`),
  getResult: (siteId: string, runId: string) =>
    req<RunResult>(`/sites/${siteId}/runs/${runId}/result`),
  decide: (siteId: string, runId: string, decision: string, edits?: string) =>
    req<Run>(`/sites/${siteId}/runs/${runId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, edits }),
    }),

  discover: (siteId: string) =>
    req<any>("/tools/discover", { method: "POST", body: JSON.stringify({ site_id: siteId }) }),
  previewImage: (prompt: string, style?: string) =>
    req<any>("/tools/preview-image", {
      method: "POST",
      body: JSON.stringify({ prompt, style }),
    }),
};
