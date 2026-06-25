import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Run, Site } from "../types";
import RunThread from "./RunThread";

const TERMINAL = new Set(["done", "rejected", "cancelled", "failed"]);
const ACTIVE = new Set([
  "queued", "discovering", "researching", "outlining", "drafting",
  "critiquing", "finalizing", "generating_images", "distributing",
]);

// Filter chips → predicate over a run's status.
const STATUS_FILTERS: { key: string; label: string; match: (s: string) => boolean }[] = [
  { key: "running", label: "Running", match: (s) => ACTIVE.has(s) && s !== "queued" },
  { key: "queued", label: "Queued", match: (s) => s === "queued" },
  { key: "awaiting_expert", label: "Awaiting review", match: (s) => s === "awaiting_expert" },
  { key: "done", label: "Done", match: (s) => s === "done" },
  { key: "failed", label: "Failed", match: (s) => s === "failed" },
  { key: "cancelled", label: "Cancelled", match: (s) => s === "cancelled" },
  { key: "rejected", label: "Rejected", match: (s) => s === "rejected" },
];

const PAGE_SIZES = [10, 25, 50];

export default function RunsPanel({ site }: { site: Site }) {
  const siteId = site.id;
  const [runs, setRuns] = useState<Run[]>([]);
  const [openRun, setOpenRun] = useState<string | null>(null);
  const [globalPublish, setGlobalPublish] = useState(false);
  const publishEnabled = !!site.publish?.enabled || globalPublish;

  // Filters / table state
  const [search, setSearch] = useState("");
  const [statusKeys, setStatusKeys] = useState<Set<string>>(new Set());
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [rowMsg, setRowMsg] = useState<Record<string, string>>({});
  const [bulkMsg, setBulkMsg] = useState("");

  // Create form
  const [showCreate, setShowCreate] = useState(false);

  async function refresh() {
    try { setRuns(await api.listRuns(siteId)); } catch (e) { setBulkMsg(String(e)); }
  }
  useEffect(() => {
    refresh();
    api.getAccount().then((a) => setGlobalPublish(a.publish_enabled)).catch(() => {});
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [siteId]);

  // ── Filter → sort → paginate ────────────────────────────────────────────────
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const fromTs = from ? new Date(from + "T00:00:00").getTime() : null;
    const toTs = to ? new Date(to + "T23:59:59").getTime() : null;
    const out = runs.filter((r) => {
      if (q && !((r.topic ?? "").toLowerCase().includes(q) || (r.keyword ?? "").toLowerCase().includes(q) || r.id.includes(q))) return false;
      if (statusKeys.size) {
        const hit = STATUS_FILTERS.some((f) => statusKeys.has(f.key) && f.match(r.status));
        if (!hit) return false;
      }
      const ts = r.created_at ? new Date(r.created_at).getTime() : 0;
      if (fromTs && ts < fromTs) return false;
      if (toTs && ts > toTs) return false;
      return true;
    });
    out.sort((a, b) => {
      const av = new Date(a.created_at ?? 0).getTime();
      const bv = new Date(b.created_at ?? 0).getTime();
      return sortDir === "desc" ? bv - av : av - bv;
    });
    return out;
  }, [runs, search, statusKeys, from, to, sortDir]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const clampedPage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(clampedPage * pageSize, clampedPage * pageSize + pageSize);
  useEffect(() => { setPage(0); }, [search, statusKeys, from, to, pageSize]);

  const selectedRuns = runs.filter((r) => selected.has(r.id));
  const pageAllSelected = pageRows.length > 0 && pageRows.every((r) => selected.has(r.id));

  function toggleStatus(key: string) {
    setStatusKeys((s) => { const n = new Set(s); n.has(key) ? n.delete(key) : n.add(key); return n; });
  }
  function toggleSel(id: string) {
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }
  function togglePageAll() {
    setSelected((s) => {
      const n = new Set(s);
      if (pageAllSelected) pageRows.forEach((r) => n.delete(r.id));
      else pageRows.forEach((r) => n.add(r.id));
      return n;
    });
  }
  function clearFilters() { setSearch(""); setStatusKeys(new Set()); setFrom(""); setTo(""); }
  function setRow(id: string, t: string) { setRowMsg((m) => ({ ...m, [id]: t })); }

  // ── Per-run actions ─────────────────────────────────────────────────────────
  async function approve(r: Run) { setRow(r.id, "Approving…"); try { await api.decide(siteId, r.id, "approve"); setRow(r.id, "Approved"); refresh(); } catch (e) { setRow(r.id, String(e)); } }
  async function cancel(r: Run) { setRow(r.id, "Cancelling…"); try { await api.cancelRun(siteId, r.id); setRow(r.id, ""); refresh(); } catch (e) { setRow(r.id, String(e)); } }
  async function publish(r: Run) { setRow(r.id, "Publishing…"); try { const x = await api.publishRun(siteId, r.id); setRow(r.id, x.url ? `Published → ${x.url}` : "Published"); } catch (e) { setRow(r.id, String(e)); } }
  async function download(r: Run) {
    setRow(r.id, "Preparing .mdx…");
    try {
      const res = await api.getResult(siteId, r.id);
      if (!res.mdx) { setRow(r.id, "No .mdx"); return; }
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([res.mdx], { type: "text/mdx" }));
      a.download = res.mdx_filename ?? `${res.slug ?? "post"}.mdx`;
      a.click(); URL.revokeObjectURL(a.href); setRow(r.id, "");
    } catch (e) { setRow(r.id, String(e)); }
  }

  // ── Bulk actions ────────────────────────────────────────────────────────────
  async function bulk(kind: "approve" | "cancel" | "publish" | "download") {
    const targets = selectedRuns.filter((r) =>
      kind === "approve" ? r.status === "awaiting_expert" :
      kind === "cancel" ? !TERMINAL.has(r.status) :
      r.status === "done");
    if (!targets.length) { setBulkMsg(`No selected runs are eligible for ${kind}.`); return; }
    setBulkMsg(`${kind[0].toUpperCase() + kind.slice(1)}ing ${targets.length}…`);
    const fn = { approve, cancel, publish, download }[kind];
    const results = await Promise.allSettled(targets.map((r) => fn(r)));
    const ok = results.filter((x) => x.status === "fulfilled").length;
    setBulkMsg(`${kind}: ${ok}/${targets.length} done.`);
    setSelected(new Set());
    refresh();
  }

  if (openRun) {
    return <RunThread siteId={siteId} runId={openRun} publishEnabled={publishEnabled}
      onBack={() => { setOpenRun(null); refresh(); }} />;
  }

  return (
    <div className="space-y-4">
      {/* Create */}
      <div className="rounded-xl border border-slate-200 bg-white">
        <button onClick={() => setShowCreate((v) => !v)}
          className="flex w-full items-center justify-between px-4 py-3 text-left font-medium">
          <span>+ New blog run</span>
          <span className="text-slate-400">{showCreate ? "▲" : "▼"}</span>
        </button>
        {showCreate && <div className="border-t p-4"><CreateForm siteId={siteId} onCreated={(id) => { refresh(); setOpenRun(id); }} onQueued={refresh} /></div>}
      </div>

      {/* Toolbar */}
      <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <input className="inp max-w-xs flex-1" placeholder="Search topic, keyword, or id…"
            value={search} onChange={(e) => setSearch(e.target.value)} />
          <label className="flex items-center gap-1 text-xs text-slate-500">From
            <input type="date" className="inp !py-1" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label className="flex items-center gap-1 text-xs text-slate-500">To
            <input type="date" className="inp !py-1" value={to} onChange={(e) => setTo(e.target.value)} /></label>
          {(search || statusKeys.size || from || to) && (
            <button onClick={clearFilters} className="text-xs text-slate-500 hover:text-slate-800 underline">clear</button>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {STATUS_FILTERS.map((f) => (
            <button key={f.key} onClick={() => toggleStatus(f.key)}
              className={`rounded-full border px-2.5 py-0.5 text-xs ${statusKeys.has(f.key) ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm">
          <span className="font-medium text-blue-800">{selected.size} selected</span>
          <BulkBtn onClick={() => bulk("approve")}>✓ Approve</BulkBtn>
          <BulkBtn onClick={() => bulk("publish")} disabled={!publishEnabled}>↗ Publish</BulkBtn>
          <BulkBtn onClick={() => bulk("download")}>⬇ Download</BulkBtn>
          <BulkBtn onClick={() => bulk("cancel")} danger>✕ Cancel</BulkBtn>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-xs text-slate-500 underline">clear selection</button>
        </div>
      )}
      {bulkMsg && <p className="px-1 text-xs text-slate-600">{bulkMsg}</p>}

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="w-10 px-3 py-2"><input type="checkbox" checked={pageAllSelected} onChange={togglePageAll} /></th>
              <th className="px-3 py-2">Topic</th>
              <th className="px-3 py-2">Status</th>
              <th className="cursor-pointer px-3 py-2 whitespace-nowrap" onClick={() => setSortDir((d) => d === "desc" ? "asc" : "desc")}>
                Created {sortDir === "desc" ? "↓" : "↑"}
              </th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {pageRows.length === 0 && (
              <tr><td colSpan={5} className="px-3 py-8 text-center text-slate-400">No runs match these filters.</td></tr>
            )}
            {pageRows.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-3 py-2"><input type="checkbox" checked={selected.has(r.id)} onChange={() => toggleSel(r.id)} /></td>
                <td className="px-3 py-2">
                  <button onClick={() => setOpenRun(r.id)} className="text-left">
                    <div className="font-medium text-slate-800">{r.topic ?? "(auto topic)"}</div>
                    <div className="font-mono text-[11px] text-slate-400">{r.id.slice(0, 10)}</div>
                    {rowMsg[r.id] && <div className="truncate text-[11px] text-slate-500">{rowMsg[r.id]}</div>}
                  </button>
                </td>
                <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
                <td className="px-3 py-2 whitespace-nowrap text-xs text-slate-500">{fmt(r.created_at)}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center justify-end gap-1">
                    {r.status === "awaiting_expert" && <Icon title="Approve" tone="green" onClick={() => approve(r)}>✓</Icon>}
                    {r.status === "done" && <Icon title="Download .mdx" tone="slate" onClick={() => download(r)}>⬇</Icon>}
                    {r.status === "done" && publishEnabled && <Icon title="Publish" tone="blue" onClick={() => publish(r)}>↗</Icon>}
                    {!TERMINAL.has(r.status) && <Icon title="Cancel" tone="red" onClick={() => cancel(r)}>✕</Icon>}
                    <Icon title="Open" tone="slate" onClick={() => setOpenRun(r.id)}>›</Icon>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <div className="flex items-center gap-2">
            <span>Rows:</span>
            <select className="rounded border border-slate-300 bg-white px-1.5 py-0.5" value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}>
              {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            <span className="ml-2">{filtered.length} run{filtered.length === 1 ? "" : "s"}</span>
          </div>
          <div className="flex items-center gap-2">
            <button disabled={clampedPage === 0} onClick={() => setPage(clampedPage - 1)}
              className="rounded border border-slate-300 bg-white px-2 py-0.5 disabled:opacity-40">‹ Prev</button>
            <span>Page {clampedPage + 1} / {pageCount}</span>
            <button disabled={clampedPage >= pageCount - 1} onClick={() => setPage(clampedPage + 1)}
              className="rounded border border-slate-300 bg-white px-2 py-0.5 disabled:opacity-40">Next ›</button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Create form (collapsible) ────────────────────────────────────────────────── */
function CreateForm({ siteId, onCreated, onQueued }: {
  siteId: string; onCreated: (id: string) => void; onQueued: () => void;
}) {
  const [topic, setTopic] = useState("");
  const [keyword, setKeyword] = useState("");
  const [insights, setInsights] = useState("");
  const [autoApprove, setAutoApprove] = useState(false);
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [bulkRows, setBulkRows] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function stageCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = "";
    if (!file) return;
    const text = await file.text();
    setBulkFile(file); setBulkRows(Math.max(0, text.split(/\r?\n/).filter((l) => l.trim()).length - 1)); setMsg("");
  }
  async function generate() {
    setBusy(true); setMsg("");
    try {
      if (bulkFile) {
        const created = await api.uploadRunsCsv(siteId, bulkFile, autoApprove);
        setMsg(`Queued ${created.length} run${created.length === 1 ? "" : "s"}.`);
        setBulkFile(null); setBulkRows(0); onQueued();
      } else {
        const r = await api.createRun(siteId, { topic: topic || null, keyword: keyword || null, expert_insights: insights || null, auto_approve: autoApprove });
        setTopic(""); setKeyword(""); setInsights(""); onCreated(r.id);
      }
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <input className="inp" placeholder="Topic (blank = auto-discover)" value={topic} onChange={(e) => setTopic(e.target.value)} disabled={!!bulkFile} />
        <input className="inp" placeholder="Primary keyword (optional)" value={keyword} onChange={(e) => setKeyword(e.target.value)} disabled={!!bulkFile} />
      </div>
      <textarea className="inp" placeholder="Expert insight — war story, real numbers, contrarian take (E-E-A-T layer)"
        value={insights} onChange={(e) => setInsights(e.target.value)} disabled={!!bulkFile} />
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-medium">Bulk upload (CSV)</span>
          <button onClick={() => api.downloadRunsTemplate(siteId)} className="rounded-md border border-slate-300 bg-white px-3 py-1.5">⬇ Template</button>
          <label className="cursor-pointer rounded-md bg-slate-900 px-3 py-1.5 text-white">
            {bulkFile ? "Choose another" : "⬆ Choose CSV"}
            <input type="file" accept=".csv,text/csv" className="hidden" onChange={stageCsv} />
          </label>
          {bulkFile && (
            <span className="flex items-center gap-2 text-xs text-slate-700">
              <span className="rounded bg-white px-2 py-0.5">{bulkFile.name} · ~{bulkRows} topic{bulkRows === 1 ? "" : "s"}</span>
              <button onClick={() => { setBulkFile(null); setBulkRows(0); }} className="text-slate-400 hover:text-red-600">clear</button>
            </span>
          )}
        </div>
        <p className="mt-2 text-xs text-slate-500">Columns: <code>topic, primary_keywords, expert_insights</code>. Nothing runs until you click Generate.</p>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={autoApprove} onChange={(e) => setAutoApprove(e.target.checked)} />
        Skip review gate (auto-approve{bulkFile ? " all" : ""})
      </label>
      <button onClick={generate} disabled={busy} className="w-full rounded-lg bg-blue-600 px-4 py-2.5 font-medium text-white disabled:opacity-50">
        {busy ? "Queuing…" : bulkFile ? `Generate ${bulkRows || ""} blogs` : "Generate blog"}
      </button>
      {msg && <p className="text-sm text-slate-600">{msg}</p>}
    </div>
  );
}

/* ── Small UI ──────────────────────────────────────────────────────────────────── */
function fmt(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "—" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function Icon({ title, tone, onClick, children }: {
  title: string; tone: "green" | "blue" | "red" | "slate"; onClick: () => void; children: React.ReactNode;
}) {
  const cls = {
    green: "text-green-700 hover:bg-green-100",
    blue: "text-blue-700 hover:bg-blue-100",
    red: "text-red-600 hover:bg-red-100",
    slate: "text-slate-500 hover:bg-slate-200",
  }[tone];
  return (
    <button title={title} onClick={(e) => { e.stopPropagation(); onClick(); }}
      className={`flex h-7 w-7 items-center justify-center rounded-md text-sm ${cls}`}>{children}</button>
  );
}

function BulkBtn({ onClick, children, danger, disabled }: {
  onClick: () => void; children: React.ReactNode; danger?: boolean; disabled?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`rounded-md border bg-white px-2.5 py-1 text-xs font-medium disabled:opacity-40 ${danger ? "border-red-300 text-red-600 hover:bg-red-50" : "border-slate-300 text-slate-700 hover:bg-slate-100"}`}>
      {children}
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "done" ? "bg-green-100 text-green-700" :
    status === "awaiting_expert" ? "bg-amber-100 text-amber-700" :
    status === "failed" || status === "rejected" ? "bg-red-100 text-red-700" :
    status === "cancelled" ? "bg-slate-200 text-slate-600" :
    ACTIVE.has(status) ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600";
  return <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs ${color}`}>{status.replace(/_/g, " ")}</span>;
}
