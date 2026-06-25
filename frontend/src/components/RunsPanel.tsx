import { useEffect, useState } from "react";
import { api } from "../api";
import type { Run } from "../types";
import RunThread from "./RunThread";

const TERMINAL = new Set(["done", "rejected", "cancelled", "failed"]);
const ACTIVE = new Set([
  "queued", "discovering", "researching", "outlining", "drafting",
  "critiquing", "finalizing", "generating_images", "distributing",
]);

export default function RunsPanel({ siteId }: { siteId: string }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [topic, setTopic] = useState("");
  const [keyword, setKeyword] = useState("");
  const [insights, setInsights] = useState("");
  const [autoApprove, setAutoApprove] = useState(false);
  const [openRun, setOpenRun] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [bulkRows, setBulkRows] = useState(0);
  const [publishEnabled, setPublishEnabled] = useState(false);
  const [rowMsg, setRowMsg] = useState<Record<string, string>>({});

  async function refresh() {
    try {
      setRuns(await api.listRuns(siteId));
    } catch (e) {
      setMsg(String(e));
    }
  }

  useEffect(() => {
    refresh();
    api.getAccount().then((a) => setPublishEnabled(a.publish_enabled)).catch(() => {});
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [siteId]);

  async function stageCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const text = await file.text();
    const rows = text.split(/\r?\n/).filter((l) => l.trim()).length;
    setBulkFile(file);
    setBulkRows(Math.max(0, rows - 1)); // minus header (rough hint; server does the real parse)
    setMsg("");
  }

  // The single entry point: a staged CSV queues many; otherwise the form queues one.
  async function generate() {
    setBusy(true); setMsg("");
    try {
      if (bulkFile) {
        const created = await api.uploadRunsCsv(siteId, bulkFile, autoApprove);
        setMsg(`Queued ${created.length} blog run${created.length === 1 ? "" : "s"}.`);
        setBulkFile(null); setBulkRows(0);
        await refresh();
      } else {
        const r = await api.createRun(siteId, {
          topic: topic || null,
          keyword: keyword || null,
          expert_insights: insights || null,
          auto_approve: autoApprove,
        });
        setTopic(""); setKeyword(""); setInsights("");
        await refresh();
        setOpenRun(r.id);
      }
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  function setRow(id: string, text: string) {
    setRowMsg((m) => ({ ...m, [id]: text }));
  }

  async function quickApprove(run: Run) {
    setRow(run.id, "Approving…");
    try { await api.decide(siteId, run.id, "approve"); setRow(run.id, "Approved — resuming"); await refresh(); }
    catch (e) { setRow(run.id, String(e)); }
  }

  async function quickCancel(run: Run) {
    setRow(run.id, "Cancelling…");
    try { await api.cancelRun(siteId, run.id); setRow(run.id, "Cancelled"); await refresh(); }
    catch (e) { setRow(run.id, String(e)); }
  }

  async function quickDownload(run: Run) {
    setRow(run.id, "Preparing .mdx…");
    try {
      const result = await api.getResult(siteId, run.id);
      if (!result.mdx) { setRow(run.id, "No .mdx available"); return; }
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([result.mdx], { type: "text/mdx" }));
      a.download = result.mdx_filename ?? `${result.slug ?? "post"}.mdx`;
      a.click();
      URL.revokeObjectURL(a.href);
      setRow(run.id, "");
    } catch (e) { setRow(run.id, String(e)); }
  }

  async function quickPublish(run: Run) {
    setRow(run.id, "Publishing…");
    try {
      const r = await api.publishRun(siteId, run.id);
      setRow(run.id, r.url ? `Published → ${r.url}` : "Published");
    } catch (e) { setRow(run.id, String(e)); }
  }

  if (openRun) {
    return <RunThread siteId={siteId} runId={openRun}
      onBack={() => { setOpenRun(null); refresh(); }} publishEnabled={publishEnabled} />;
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
        <h3 className="font-medium">New blog run</h3>
        <div className="grid grid-cols-2 gap-3">
          <input className="inp" placeholder="Topic (blank = auto-discover)" value={topic}
            onChange={(e) => setTopic(e.target.value)} disabled={!!bulkFile} />
          <input className="inp" placeholder="Primary keyword (optional)" value={keyword}
            onChange={(e) => setKeyword(e.target.value)} disabled={!!bulkFile} />
        </div>
        <textarea className="inp"
          placeholder="Expert insight — war story, real numbers, contrarian take (E-E-A-T layer)"
          value={insights} onChange={(e) => setInsights(e.target.value)} disabled={!!bulkFile} />

        {/* Bulk CSV — staged, not started until you click Generate. */}
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-medium">Bulk upload (CSV)</span>
            <button onClick={() => api.downloadRunsTemplate(siteId)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5">⬇ Template</button>
            <label className="cursor-pointer rounded-md bg-slate-900 px-3 py-1.5 text-white">
              {bulkFile ? "Choose another" : "⬆ Choose CSV"}
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={stageCsv} />
            </label>
            {bulkFile && (
              <span className="flex items-center gap-2 text-xs text-slate-700">
                <span className="rounded bg-white px-2 py-0.5">{bulkFile.name} · ~{bulkRows} topic{bulkRows === 1 ? "" : "s"}</span>
                <button onClick={() => { setBulkFile(null); setBulkRows(0); }}
                  className="text-slate-400 hover:text-red-600">clear</button>
              </span>
            )}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Columns: <code>topic, primary_keywords, expert_insights</code>. One blog is queued per row.
            Nothing runs until you click <strong>Generate</strong>.
          </p>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={autoApprove} onChange={(e) => setAutoApprove(e.target.checked)} />
          Skip review gate (auto-approve{bulkFile ? " all" : ""})
        </label>

        {/* Generate lives below the CSV box — runs the staged CSV or the single form. */}
        <button onClick={generate} disabled={busy}
          className="w-full rounded-lg bg-blue-600 px-4 py-2.5 font-medium text-white disabled:opacity-50">
          {busy ? "Queuing…" : bulkFile ? `Generate ${bulkRows || ""} blogs` : "Generate blog"}
        </button>
        {msg && <p className="text-sm text-slate-600">{msg}</p>}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b px-4 py-2 font-medium">Runs</div>
        <ul className="divide-y">
          {runs.length === 0 && <li className="px-4 py-3 text-sm text-slate-400">No runs yet.</li>}
          {runs.map((r) => {
            const active = !TERMINAL.has(r.status);
            return (
              <li key={r.id} className="px-4 py-3 hover:bg-slate-50">
                <div className="flex items-center justify-between gap-3">
                  <button onClick={() => setOpenRun(r.id)} className="min-w-0 flex-1 text-left">
                    <div className="truncate font-medium">{r.topic ?? "(auto topic)"}</div>
                    <div className="truncate text-xs text-slate-500">{r.id}</div>
                  </button>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    {r.status === "awaiting_expert" && (
                      <ActionBtn tone="green" onClick={() => quickApprove(r)}>✓ Approve</ActionBtn>
                    )}
                    {r.status === "done" && (
                      <ActionBtn tone="slate" onClick={() => quickDownload(r)}>⬇ .mdx</ActionBtn>
                    )}
                    {r.status === "done" && publishEnabled && (
                      <ActionBtn tone="blue" onClick={() => quickPublish(r)}>↗ Publish</ActionBtn>
                    )}
                    {active && (
                      <ActionBtn tone="red" onClick={() => quickCancel(r)}>✕ Cancel</ActionBtn>
                    )}
                    <StatusBadge status={r.status} />
                  </div>
                </div>
                {rowMsg[r.id] && <p className="mt-1 truncate text-xs text-slate-500">{rowMsg[r.id]}</p>}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function ActionBtn({ tone, onClick, children }: {
  tone: "green" | "blue" | "red" | "slate"; onClick: () => void; children: React.ReactNode;
}) {
  const cls = {
    green: "border-green-600 text-green-700 hover:bg-green-50",
    blue: "border-blue-600 text-blue-700 hover:bg-blue-50",
    red: "border-red-300 text-red-600 hover:bg-red-50",
    slate: "border-slate-300 text-slate-700 hover:bg-slate-100",
  }[tone];
  return (
    <button onClick={(e) => { e.stopPropagation(); onClick(); }}
      className={`rounded-md border bg-white px-2.5 py-1 text-xs font-medium ${cls}`}>
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
  return <span className={`rounded-full px-2 py-0.5 text-xs ${color}`}>{status.replace(/_/g, " ")}</span>;
}
