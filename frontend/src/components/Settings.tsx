import { useEffect, useState } from "react";
import { api } from "../api";
import type { Account } from "../types";

const KEY_FIELDS: { key: string; label: string; hint: string }[] = [
  { key: "gemini_key", label: "Gemini API key", hint: "Required to generate posts and images." },
  { key: "langsmith_key", label: "LangSmith key", hint: "Optional — pipeline tracing." },
  { key: "serp_key", label: "SERP key", hint: "Optional — paid discovery sources." },
];

export default function Settings() {
  const [account, setAccount] = useState<Account | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.getAccount().then(setAccount).catch((e) => setMsg(String(e)));
  }, []);

  async function save() {
    setSaving(true);
    setMsg("");
    try {
      const payload = Object.fromEntries(Object.entries(edits).filter(([, v]) => v));
      const updated = await api.setKeys(payload);
      setAccount(updated);
      setEdits({});
      setMsg("Saved.");
    } catch (e) {
      setMsg(String(e));
    } finally {
      setSaving(false);
    }
  }

  if (!account) return <div className="text-slate-500">Loading account…</div>;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Account</h2>
        <p className="text-sm text-slate-500">{account.email ?? account.uid} · {account.plan}</p>
      </div>
      <div className="space-y-4">
        <h3 className="font-medium">Provider keys (BYOK)</h3>
        <p className="text-sm text-slate-500">
          Keys are encrypted at rest. Saved keys show only the last 4 characters.
        </p>
        {KEY_FIELDS.map((f) => (
          <div key={f.key} className="space-y-1">
            <label className="text-sm font-medium">{f.label}</label>
            <input
              type="password"
              placeholder={account.keys[f.key] ?? "not set"}
              value={edits[f.key] ?? ""}
              onChange={(e) => setEdits({ ...edits, [f.key]: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
            />
            <p className="text-xs text-slate-400">{f.hint}</p>
          </div>
        ))}
        <button
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save keys"}
        </button>
        {msg && <span className="ml-3 text-sm text-slate-600">{msg}</span>}
      </div>
    </div>
  );
}
