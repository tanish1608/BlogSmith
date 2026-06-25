import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api";
import type { Run, RunResult } from "../types";

const STEPS = [
  { key: "discovery", label: "Discovery", blurb: "Find the best buyer-intent topic" },
  { key: "research", label: "Research", blurb: "Gather facts & primary sources" },
  { key: "outline", label: "Outline", blurb: "Structure to search intent" },
  { key: "draft", label: "Draft", blurb: "Write in your brand voice" },
  { key: "critique", label: "Critique", blurb: "Edit, kill AI tells, SEO check" },
  { key: "expert", label: "Expert review", blurb: "Your approve / edit / reject", gate: true },
  { key: "final", label: "Finalize", blurb: "Title, meta, schema, slug" },
  { key: "visuals", label: "Visuals", blurb: "Generate & embed images" },
  { key: "distribution", label: "Distribute", blurb: "LinkedIn thread" },
] as const;

const ACTIVE_FOR: Record<string, string> = {
  discovering: "discovery", researching: "research", outlining: "outline",
  drafting: "draft", critiquing: "critique", awaiting_expert: "expert",
  finalizing: "final", generating_images: "visuals", distributing: "distribution",
};

const TERMINAL = new Set(["done", "rejected", "failed"]);

type StepState = "done" | "active" | "paused" | "pending" | "error" | "rejected";

export default function RunThread({ siteId, runId, onBack, publishEnabled = false }: {
  siteId: string; runId: string; onBack: () => void; publishEnabled?: boolean;
}) {
  const [run, setRun] = useState<Run | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [cancelMsg, setCancelMsg] = useState("");

  async function cancel() {
    setCancelMsg("Cancelling…");
    try { await api.cancelRun(siteId, runId); setCancelMsg("Cancelled."); }
    catch (e) { setCancelMsg(String(e)); }
  }

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const r = await api.getRun(siteId, runId);
        if (!alive) return;
        setRun(r);
        return TERMINAL.has(r.status);
      } catch (e) {
        if (alive) setErr(String(e));
        return true;
      }
    }
    tick();
    const t = setInterval(async () => {
      const done = await tick();
      if (done) clearInterval(t);
    }, 2500);
    return () => { alive = false; clearInterval(t); };
  }, [siteId, runId]);

  const activeKey = run ? ACTIVE_FOR[run.status] : undefined;

  // Auto-open the active / paused step.
  useEffect(() => { if (activeKey) setOpen(activeKey); }, [activeKey]);

  function sliceDone(key: string): boolean {
    if (!run) return false;
    if (key === "expert") {
      const e = run.stages.expert;
      return !!e && e.decision && e.decision !== "pending" && e.decision !== "reject";
    }
    return !!run.stages[key];
  }

  function stepState(key: string): StepState {
    if (!run) return "pending";
    if (run.stages.expert?.decision === "reject" && key === "expert") return "rejected";
    if (sliceDone(key)) return "done";
    if (run.status === "done") return "done";
    if (key === activeKey) return key === "expert" ? "paused" : "active";
    if (run.status === "failed") {
      const firstPending = STEPS.find((s) => !sliceDone(s.key));
      if (firstPending?.key === key) return "error";
    }
    return "pending";
  }

  const progress = useMemo(() => {
    const done = STEPS.filter((s) => stepState(s.key) === "done").length;
    return Math.round((done / STEPS.length) * 100);
  }, [run]);

  if (err) return <div className="text-red-600">{err}</div>;
  if (!run) return <div className="text-slate-500">Loading run…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="text-sm text-slate-500 hover:text-slate-800">← Back to runs</button>
        <div className="flex items-center gap-2">
          {!TERMINAL.has(run.status) && (
            <button onClick={cancel}
              className="rounded-md border border-red-300 bg-white px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50">
              ✕ Cancel run
            </button>
          )}
          <StatusPill status={run.status} />
        </div>
      </div>
      {cancelMsg && <p className="text-right text-xs text-slate-500">{cancelMsg}</p>}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">{run.topic ?? "(auto-discovered topic)"}</h2>
            <p className="text-xs text-slate-400">run {run.id}</p>
          </div>
          <span className="text-sm text-slate-500">{progress}%</span>
        </div>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div className="h-full bg-blue-600 transition-all" style={{ width: `${progress}%` }} />
        </div>
        {run.error && <p className="mt-2 text-sm text-red-600">Error: {run.error}</p>}
      </div>

      {/* The thread */}
      <ol className="relative ml-3 border-l-2 border-slate-200">
        {STEPS.map((step) => {
          const st = stepState(step.key);
          const isOpen = open === step.key;
          const slice = run.stages[step.key];
          return (
            <li key={step.key} className="ml-6 mb-3">
              <span className="absolute -left-[13px] mt-1.5">{dot(st)}</span>
              <button
                onClick={() => setOpen(isOpen ? null : step.key)}
                className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left hover:bg-slate-50"
              >
                <span>
                  <span className="font-medium">{step.label}</span>
                  <span className="ml-2 text-xs text-slate-400">{step.blurb}</span>
                </span>
                <span className="text-xs text-slate-400">{labelFor(st)}</span>
              </button>

              {isOpen && (
                <div className="mt-1 rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm">
                  {step.key === "expert" && st === "paused" ? (
                    <GatePanel siteId={siteId} run={run} />
                  ) : slice ? (
                    <StageContent stage={step.key} data={slice} />
                  ) : (
                    <span className="text-slate-400">No output yet.</span>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      {run.status === "done" && <ResultCard siteId={siteId} runId={runId} publishEnabled={publishEnabled} />}
    </div>
  );
}

/* ── The review gate (in-dashboard, replaces email) ───────────────────────── */
function GatePanel({ siteId, run }: { siteId: string; run: Run }) {
  const current =
    run.stages.critique?.edited_markdown ?? run.stages.draft?.markdown ?? "";
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [body, setBody] = useState(current);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function send(decision: string, edits?: string) {
    setBusy(true); setMsg("");
    try {
      await api.decide(siteId, run.id, decision, edits);
      setMsg(`Submitted: ${decision}. Resuming…`);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-slate-600">
        Add your war story, real numbers, or contrarian take — then approve. This is the
        E-E-A-T layer that decides whether you rank.
      </p>
      {mode === "view" ? (
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded bg-white p-3 text-xs">{current}</pre>
      ) : (
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          className="h-72 w-full rounded border border-slate-300 p-3 font-mono text-xs"
        />
      )}
      <div className="flex flex-wrap gap-2">
        <button disabled={busy} onClick={() => send("approve")}
          className="rounded-lg bg-green-600 px-4 py-2 text-white disabled:opacity-50">✓ Approve & publish</button>
        {mode === "view" ? (
          <button onClick={() => setMode("edit")}
            className="rounded-lg bg-blue-600 px-4 py-2 text-white">✎ Edit</button>
        ) : (
          <button disabled={busy} onClick={() => send("edit", body)}
            className="rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-50">Save edits & publish</button>
        )}
        <button disabled={busy} onClick={() => send("reject")}
          className="rounded-lg bg-red-50 px-4 py-2 text-red-600 disabled:opacity-50">✕ Reject</button>
      </div>
      {msg && <p className="text-xs text-slate-600">{msg}</p>}
    </div>
  );
}

/* ── Per-stage content renderers ──────────────────────────────────────────── */
function StageContent({ stage, data }: { stage: string; data: any }) {
  if (stage === "discovery") {
    return (
      <div className="space-y-2">
        {data.selected && <Kv k="Selected" v={`${data.selected.title} — ${data.selected.primary_keyword}`} />}
        {(data.topics ?? []).slice(0, 6).map((t: any, i: number) => (
          <div key={i} className="flex justify-between rounded bg-white px-2 py-1">
            <span>{t.title}</span>
            <span className="text-xs text-slate-400">{t.search_intent} · {t.buyer_intent_score}</span>
          </div>
        ))}
      </div>
    );
  }
  if (stage === "research") {
    return (
      <div className="space-y-2">
        <p className="text-slate-700">{data.summary}</p>
        {(data.key_facts ?? []).map((f: any, i: number) => (
          <div key={i} className="flex items-start gap-2">
            <Badge ok={f.status === "verified"}>{f.status}</Badge>
            <span>{f.fact}{f.source ? <em className="text-slate-400"> — {f.source}</em> : null}</span>
          </div>
        ))}
      </div>
    );
  }
  if (stage === "outline") {
    return (
      <div className="space-y-1">
        <div className="font-medium">{data.h1}</div>
        {(data.sections ?? []).map((s: any, i: number) => (
          <div key={i} className="pl-3">• {s.heading} <span className="text-xs text-slate-400">— {s.purpose}</span></div>
        ))}
      </div>
    );
  }
  if (stage === "draft") return <Md text={data.markdown} />;
  if (stage === "critique") {
    return (
      <div className="space-y-2">
        {data.seo && <Kv k="SEO score" v={`${data.seo.score}/100 · ${data.seo.word_count} words`} />}
        {(data.checklist ?? []).map((c: any, i: number) => (
          <div key={i} className="flex items-center gap-2"><Badge ok={c.pass}>{c.pass ? "pass" : "fail"}</Badge>{c.item}</div>
        ))}
        {data.ai_tells_found?.length > 0 && <Kv k="AI tells removed" v={data.ai_tells_found.join(", ")} />}
      </div>
    );
  }
  if (stage === "expert") return <Kv k="Decision" v={data.decision} />;
  if (stage === "final") {
    return (
      <div className="space-y-1">
        <Kv k="Title" v={data.title} />
        <Kv k="Meta" v={data.meta_description} />
        <Kv k="Slug" v={data.slug} />
        <Kv k="Images planned" v={String((data.images ?? []).length)} />
      </div>
    );
  }
  if (stage === "visuals") {
    return (
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          {(data.images ?? []).map((img: any, i: number) =>
            img.url ? <img key={i} src={img.url} alt={img.alt} className="h-20 rounded border" />
              : <span key={i} className="rounded bg-white px-2 py-1 text-xs text-slate-500">{img.mermaid ? "mermaid diagram" : "skipped"} · {img.type}</span>
          )}
        </div>
        <Md text={data.markdown} />
      </div>
    );
  }
  if (stage === "distribution") {
    return (
      <ol className="list-decimal space-y-1 pl-5">
        {(data.linkedin_thread ?? []).map((p: string, i: number) => <li key={i}>{p}</li>)}
      </ol>
    );
  }
  return <pre className="overflow-auto text-xs">{JSON.stringify(data, null, 2)}</pre>;
}

function ResultCard({ siteId, runId, publishEnabled }: {
  siteId: string; runId: string; publishEnabled: boolean;
}) {
  const [result, setResult] = useState<RunResult | null>(null);
  const [pubMsg, setPubMsg] = useState("");
  const [pubBusy, setPubBusy] = useState(false);
  useEffect(() => {
    api.getResult(siteId, runId).then(setResult);
  }, [siteId, runId]);

  async function publish() {
    setPubBusy(true); setPubMsg("");
    try {
      const r = await api.publishRun(siteId, runId);
      setPubMsg(r.url ? `Published → ${r.url}${r.draft ? " (draft)" : ""}` : "Published.");
    } catch (e) {
      setPubMsg(String(e));
    } finally {
      setPubBusy(false);
    }
  }

  function downloadFile(text: string, name: string, mime: string) {
    const blob = new Blob([text], { type: mime });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
  }

  const slug = result?.slug ?? "post";
  const mdx = result?.mdx ?? null;
  const md = result?.markdown ?? "";

  return (
    <div className="rounded-xl border border-green-200 bg-green-50 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-green-800">Published draft ready</h3>
        <div className="flex gap-2">
          <button
            disabled={!mdx}
            onClick={() => mdx && downloadFile(mdx, result?.mdx_filename ?? `${slug}.mdx`, "text/mdx")}
            className="rounded-lg bg-green-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >⬇ Download .mdx</button>
          <button
            onClick={() => downloadFile(md, `${slug}.md`, "text/markdown")}
            className="rounded-lg border border-green-700 px-3 py-1.5 text-sm text-green-800"
          >.md</button>
          {publishEnabled && (
            <button
              disabled={pubBusy || !mdx}
              onClick={publish}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >{pubBusy ? "Publishing…" : "↗ Publish"}</button>
          )}
        </div>
      </div>
      {pubMsg && <p className="mt-2 break-all text-xs text-slate-700">{pubMsg}</p>}
      {result?.tags && result.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {result.content_type && (
            <span className="rounded bg-green-200 px-1.5 py-0.5 text-xs text-green-900">{result.content_type}</span>
          )}
          {result.tags.map((t) => (
            <span key={t} className="rounded bg-white px-1.5 py-0.5 text-xs text-green-700">#{t}</span>
          ))}
        </div>
      )}
      {mdx && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm text-green-800">View frontmatter</summary>
          <pre className="mt-1 overflow-auto rounded bg-white p-2 text-xs text-slate-700">{mdx.split("---")[1]?.trim()}</pre>
        </details>
      )}
      {md && <Md text={md} />}
    </div>
  );
}

/* ── Small UI helpers ─────────────────────────────────────────────────────── */
function dot(state: StepState) {
  const base = "flex h-6 w-6 items-center justify-center rounded-full text-xs text-white";
  if (state === "done") return <span className={`${base} bg-green-600`}>✓</span>;
  if (state === "active") return <span className={`${base} bg-blue-600 animate-pulse`}>●</span>;
  if (state === "paused") return <span className={`${base} bg-amber-500`}>⏸</span>;
  if (state === "error") return <span className={`${base} bg-red-600`}>!</span>;
  if (state === "rejected") return <span className={`${base} bg-red-600`}>✕</span>;
  return <span className={`${base} border border-slate-300 bg-white !text-slate-400`}>○</span>;
}
function labelFor(s: StepState) {
  return { done: "done", active: "running…", paused: "needs you", pending: "", error: "failed", rejected: "rejected" }[s];
}
function StatusPill({ status }: { status: string }) {
  const color =
    status === "done" ? "bg-green-100 text-green-700" :
    status === "awaiting_expert" ? "bg-amber-100 text-amber-700" :
    status === "failed" || status === "rejected" ? "bg-red-100 text-red-700" :
    "bg-blue-100 text-blue-700";
  return <span className={`rounded-full px-3 py-1 text-xs font-medium ${color}`}>{status.replace(/_/g, " ")}</span>;
}
function Kv({ k, v }: { k: string; v: string }) {
  return <div><span className="text-slate-400">{k}: </span><span>{v}</span></div>;
}
function Badge({ ok, children }: { ok: boolean; children: ReactNode }) {
  return <span className={`rounded px-1.5 py-0.5 text-xs ${ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>{children}</span>;
}
function Md({ text }: { text?: string | null }) {
  if (!text) return null;
  return <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded bg-white p-3 text-xs">{text}</pre>;
}
