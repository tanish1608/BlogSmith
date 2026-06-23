import { useEffect, useState } from "react";
import { api } from "../api";
import type { Run } from "../types";
import RunThread from "./RunThread";

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

  async function refresh() {
    try {
      setRuns(await api.listRuns(siteId));
    } catch (e) {
      setMsg(String(e));
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [siteId]);

  async function create() {
    setMsg("");
    try {
      const r = await api.createRun(siteId, {
        topic: topic || null,
        keyword: keyword || null,
        expert_insights: insights || null,
        auto_approve: autoApprove,
      });
      setTopic(""); setKeyword(""); setInsights("");
      await refresh();
      setOpenRun(r.id);
    } catch (e) {
      setMsg(String(e));
    }
  }

  if (openRun) {
    return <RunThread siteId={siteId} runId={openRun} onBack={() => { setOpenRun(null); refresh(); }} />;
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
        <h3 className="font-medium">New blog run</h3>
        <div className="grid grid-cols-2 gap-3">
          <input className="inp" placeholder="Topic (blank = auto-discover)" value={topic}
            onChange={(e) => setTopic(e.target.value)} />
          <input className="inp" placeholder="Primary keyword (optional)" value={keyword}
            onChange={(e) => setKeyword(e.target.value)} />
        </div>
        <textarea className="inp"
          placeholder="Expert insight — war story, real numbers, contrarian take (E-E-A-T layer)"
          value={insights} onChange={(e) => setInsights(e.target.value)} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={autoApprove} onChange={(e) => setAutoApprove(e.target.checked)} />
          Skip review gate (auto-approve)
        </label>
        <button onClick={create} className="rounded-lg bg-blue-600 px-4 py-2 text-white">Generate blog</button>
        {msg && <p className="text-sm text-red-600">{msg}</p>}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b px-4 py-2 font-medium">Runs</div>
        <ul className="divide-y">
          {runs.length === 0 && <li className="px-4 py-3 text-sm text-slate-400">No runs yet.</li>}
          {runs.map((r) => (
            <li key={r.id}>
              <button onClick={() => setOpenRun(r.id)}
                className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-slate-50">
                <div>
                  <div className="font-medium">{r.topic ?? "(auto topic)"}</div>
                  <div className="text-xs text-slate-500">{r.id}</div>
                </div>
                <StatusBadge status={r.status} />
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "done" ? "bg-green-100 text-green-700" :
    status === "awaiting_expert" ? "bg-amber-100 text-amber-700" :
    status === "failed" || status === "rejected" ? "bg-red-100 text-red-700" :
    ACTIVE.has(status) ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600";
  return <span className={`rounded-full px-2 py-0.5 text-xs ${color}`}>{status.replace(/_/g, " ")}</span>;
}
