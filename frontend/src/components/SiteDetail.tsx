import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api";
import type { Site } from "../types";
import RunsPanel from "./RunsPanel";

const PROMPT_STAGES = [
  "discovery", "research", "outline", "draft", "critique", "finalize", "visuals", "distribute",
] as const;

export default function SiteDetail({ site, onSaved, onDeleted }: {
  site: Site;
  onSaved: (s: Site) => void;
  onDeleted: () => void;
}) {
  const [tab, setTab] = useState<"config" | "runs">("runs");
  const [draft, setDraft] = useState<Site>(site);
  const [msg, setMsg] = useState("");

  // Re-sync the editable form whenever the site prop changes (e.g. after a CSV
  // import returns the updated site) so imported values show up in the fields.
  useEffect(() => { setDraft(site); }, [site]);

  function set<K extends keyof Site>(key: K, value: Site[K]) {
    setDraft({ ...draft, [key]: value });
  }
  function setPrompt(stage: string, value: string) {
    setDraft({ ...draft, custom_prompts: { ...draft.custom_prompts, [stage]: value } });
  }
  function setAuthor(field: "name" | "role" | "url", value: string) {
    setDraft({ ...draft, author: { ...(draft.author ?? {}), [field]: value } });
  }

  async function save() {
    setMsg("");
    try {
      const updated = await api.updateSite(site.id, {
        name: draft.name,
        domain: draft.domain,
        brand_voice: draft.brand_voice,
        image_style: draft.image_style,
        content_type: draft.content_type,
        default_tags: draft.default_tags,
        author: draft.author,
        custom_prompts: draft.custom_prompts,
        discovery: draft.discovery,
        schedule: draft.schedule,
        approval_email: draft.approval_email,
      });
      onSaved(updated);
      setMsg("Saved.");
    } catch (e) {
      setMsg(String(e));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">{site.name}</h2>
          <p className="text-sm text-slate-500">{site.domain}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setTab("runs")}
            className={`rounded-lg px-3 py-1.5 text-sm ${tab === "runs" ? "bg-slate-900 text-white" : "bg-slate-100"}`}>Runs</button>
          <button onClick={() => setTab("config")}
            className={`rounded-lg px-3 py-1.5 text-sm ${tab === "config" ? "bg-slate-900 text-white" : "bg-slate-100"}`}>Config</button>
        </div>
      </div>

      {tab === "runs" && <RunsPanel siteId={site.id} />}

      {tab === "config" && (
        <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-4">
          <ConfigCsvBox site={site} onImported={onSaved} />
          <Field label="Name"><input className="inp" value={draft.name} onChange={(e) => set("name", e.target.value)} /></Field>
          <Field label="Domain"><input className="inp" value={draft.domain} onChange={(e) => set("domain", e.target.value)} /></Field>
          <Field label="Approval email"><input className="inp" value={draft.approval_email ?? ""} onChange={(e) => set("approval_email", e.target.value)} /></Field>
          <Field label="Brand voice"><textarea className="inp" value={draft.brand_voice ?? ""} onChange={(e) => set("brand_voice", e.target.value)} /></Field>
          <Field label="Image style"><input className="inp" value={draft.image_style ?? ""} onChange={(e) => set("image_style", e.target.value)} /></Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Content type (MDX 'type')">
              <select className="inp" value={draft.content_type ?? "guide"}
                onChange={(e) => set("content_type", e.target.value)}>
                {["guide", "teardown", "explainer", "comparison", "checklist", "opinion", "tutorial"].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </Field>
            <Field label="Default tags (comma separated)">
              <input className="inp" value={(draft.default_tags ?? []).join(", ")}
                onChange={(e) => set("default_tags", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))} />
            </Field>
          </div>

          <div>
            <h3 className="font-medium mb-2">Author (MDX frontmatter byline)</h3>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Name"><input className="inp" value={draft.author?.name ?? ""} onChange={(e) => setAuthor("name", e.target.value)} /></Field>
              <Field label="Role"><input className="inp" value={draft.author?.role ?? ""} onChange={(e) => setAuthor("role", e.target.value)} /></Field>
              <Field label="URL"><input className="inp" value={draft.author?.url ?? ""} onChange={(e) => setAuthor("url", e.target.value)} /></Field>
            </div>
          </div>

          <Field label="Seed topics (comma separated)">
            <input className="inp" value={(draft.discovery.seed_topics || []).join(", ")}
              onChange={(e) => set("discovery", { ...draft.discovery, seed_topics: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
          </Field>

          <div>
            <h3 className="font-medium mb-2">Custom prompts (layered on the defaults)</h3>
            <div className="space-y-3">
              {PROMPT_STAGES.map((stage) => (
                <Field key={stage} label={stage}>
                  <textarea className="inp" rows={2}
                    value={(draft.custom_prompts as any)[stage] ?? ""}
                    onChange={(e) => setPrompt(stage, e.target.value)} />
                </Field>
              ))}
            </div>
          </div>

          <div>
            <h3 className="font-medium mb-2">Schedule</h3>
            <label className="flex items-center gap-2 text-sm mb-2">
              <input type="checkbox" checked={draft.schedule.enabled}
                onChange={(e) => set("schedule", { ...draft.schedule, enabled: e.target.checked })} />
              Enabled
            </label>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Cadence">
                <select className="inp" value={draft.schedule.cadence}
                  onChange={(e) => set("schedule", { ...draft.schedule, cadence: e.target.value })}>
                  <option value="daily">daily</option>
                  <option value="weekly">weekly</option>
                </select>
              </Field>
              <Field label="Timezone">
                <input className="inp" value={draft.schedule.timezone}
                  onChange={(e) => set("schedule", { ...draft.schedule, timezone: e.target.value })} />
              </Field>
              <Field label="Times (comma, HH:MM)">
                <input className="inp" value={draft.schedule.times.join(", ")}
                  onChange={(e) => set("schedule", { ...draft.schedule, times: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
              </Field>
              <Field label="Blogs per fire">
                <input type="number" className="inp" value={draft.schedule.count_per_run}
                  onChange={(e) => set("schedule", { ...draft.schedule, count_per_run: Number(e.target.value) })} />
              </Field>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button onClick={save} className="rounded-lg bg-blue-600 px-4 py-2 text-white">Save config</button>
            <button onClick={async () => { await api.deleteSite(site.id); onDeleted(); }}
              className="rounded-lg bg-red-50 px-4 py-2 text-red-600">Delete site</button>
            {msg && <span className="text-sm text-slate-600">{msg}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium capitalize">{label}</span>
      {children}
    </label>
  );
}

function ConfigCsvBox({ site, onImported }: { site: Site; onImported: (s: Site) => void }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-upload of the same file
    if (!file) return;
    setBusy(true); setMsg("");
    try {
      const updated = await api.uploadConfigCsv(site.id, file);
      onImported(updated);
      setMsg("Config imported. Name and domain were left unchanged.");
    } catch (err) {
      setMsg(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-medium">Config as CSV</span>
        <button onClick={() => api.downloadConfigCsv(site.id)}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5">⬇ Download template</button>
        <label className="cursor-pointer rounded-md bg-slate-900 px-3 py-1.5 text-white">
          {busy ? "Importing…" : "⬆ Upload CSV"}
          <input type="file" accept=".csv,text/csv" className="hidden" onChange={onUpload} disabled={busy} />
        </label>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Download your current config, edit the values, and re-upload. <strong>Name and domain are
        locked</strong> — edits to those rows are ignored.
      </p>
      {msg && <p className="mt-1 text-xs text-slate-700">{msg}</p>}
    </div>
  );
}
