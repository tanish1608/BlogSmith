import { useEffect, useState } from "react";
import { api } from "../api";
import type { Run, RunResult } from "../types";

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
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);
  const [msg, setMsg] = useState("");

  async function refresh() {
    try {
      setRuns(await api.listRuns(siteId));
    } catch (e) {
      setMsg(String(e));
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000); // poll for live status
    return () => clearInterval(t);
  }, [siteId]);

  async function create() {
    setMsg("");
    try {
      await api.createRun(siteId, {
        topic: topic || null,
        keyword: keyword || null,
        expert_insights: insights || null,
        auto_approve: autoApprove,
      });
      setTopic(""); setKeyword(""); setInsights("");
      refresh();
    } catch (e) {
      setMsg(String(e));
    }
  }

  async function open(runId: string) {
    setSelected(runId);
    setResult(null);
    try {
      setResult(await api.getResult(siteId, runId));
    } catch (e) {
      setMsg(String(e));
    }
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
        <h3 className="font-medium">New blog run</h3>
        <div className="grid grid-cols-2 gap-3">
          <input className="rounded-lg border border-slate-300 px-3 py-2"
            placeholder="Topic (blank = auto-discover)" value={topic}
            onChange={(e) => setTopic(e.target.value)} />
          <input className="rounded-lg border border-slate-300 px-3 py-2"
            placeholder="Primary keyword (optional)" value={keyword}
            onChange={(e) => setKeyword(e.target.value)} />
        </div>
        <textarea className="w-full rounded-lg border border-slate-300 px-3 py-2"
          placeholder="Expert insight — war story, real numbers, contrarian take (E-E-A-T layer)"
          value={insights} onChange={(e) => setInsights(e.target.value)} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={autoApprove}
            onChange={(e) => setAutoApprove(e.target.checked)} />
          Skip email gate (auto-approve)
        </label>
        <button onClick={create} className="rounded-lg bg-blue-600 px-4 py-2 text-white">
          Generate blog
        </button>
        {msg && <p className="text-sm text-red-600">{msg}</p>}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b px-4 py-2 font-medium">Runs</div>
        <ul className="divide-y">
          {runs.length === 0 && <li className="px-4 py-3 text-sm text-slate-400">No runs yet.</li>}
          {runs.map((r) => (
            <li key={r.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <div className="font-medium">{r.topic ?? "(auto topic)"}</div>
                <div className="text-xs text-slate-500">{r.id}</div>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={r.status} />
                <button onClick={() => open(r.id)} className="text-sm text-blue-600">View</button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {selected && result && <ResultView result={result} />}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "done" ? "bg-green-100 text-green-700" :
    status === "awaiting_expert" ? "bg-amber-100 text-amber-700" :
    status === "failed" || status === "rejected" ? "bg-red-100 text-red-700" :
    ACTIVE.has(status) ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600";
  return <span className={`rounded-full px-2 py-0.5 text-xs ${color}`}>{status}</span>;
}

function ResultView({ result }: { result: RunResult }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
      <h3 className="font-medium">{result.title ?? "Result"}</h3>
      <p className="text-sm text-slate-500">{result.meta_description}</p>
      {result.slug && <p className="text-xs text-slate-400">/{result.slug}</p>}
      {result.images?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {result.images.map((img: any, i: number) =>
            img.url ? <img key={i} src={img.url} alt={img.alt} className="h-24 rounded border" /> : null
          )}
        </div>
      )}
      {result.markdown && (
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm">
          {result.markdown}
        </pre>
      )}
      {result.linkedin_thread?.length > 0 && (
        <div>
          <h4 className="font-medium text-sm">LinkedIn thread</h4>
          <ol className="list-decimal pl-5 text-sm text-slate-700 space-y-1">
            {result.linkedin_thread.map((p, i) => <li key={i}>{p}</li>)}
          </ol>
        </div>
      )}
    </div>
  );
}
