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

/** Download a file from an authenticated endpoint and trigger a browser save. */
async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const token = await getToken();
  const res = await fetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const match = cd.match(/filename="?([^"]+)"?/);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = match?.[1] || fallbackName;
  a.click();
  URL.revokeObjectURL(a.href);
}

/** Upload a file via multipart/form-data to an authenticated endpoint. */
async function uploadFile<T>(path: string, file: File): Promise<T> {
  const token = await getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(path, {
    method: "POST",
    body: form,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<any>("/health"),

  getAccount: () => req<Account>("/account"),

  listSites: () => req<Site[]>("/sites"),
  createSite: (site: Partial<Site>) =>
    req<Site>("/sites", { method: "POST", body: JSON.stringify(site) }),
  updateSite: (id: string, patch: Partial<Site>) =>
    req<Site>(`/sites/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteSite: (id: string) => req<void>(`/sites/${id}`, { method: "DELETE" }),

  downloadConfigCsv: (siteId: string) =>
    downloadFile(`/sites/${siteId}/config.csv`, "config.csv"),
  uploadConfigCsv: (siteId: string, file: File) =>
    uploadFile<Site>(`/sites/${siteId}/config-csv`, file),

  listRuns: (siteId: string) => req<Run[]>(`/sites/${siteId}/runs`),
  createRun: (siteId: string, body: any) =>
    req<Run>(`/sites/${siteId}/runs`, { method: "POST", body: JSON.stringify(body) }),
  downloadRunsTemplate: (siteId: string) =>
    downloadFile(`/sites/${siteId}/runs/template.csv`, "blogs-template.csv"),
  uploadRunsCsv: (siteId: string, file: File, autoApprove = false) =>
    uploadFile<Run[]>(`/sites/${siteId}/runs/csv?auto_approve=${autoApprove}`, file),
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
