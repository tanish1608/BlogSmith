import { useEffect, useState } from "react";
import { api } from "../api";
import type { Account } from "../types";

const KEY_FIELDS: { key: string; label: string; env: string; hint: string }[] = [
  { key: "gemini_key", label: "Gemini API key", env: "GEMINI_API_KEY", hint: "Required to generate posts and images." },
  { key: "langsmith_key", label: "LangSmith key", env: "LANGSMITH_API_KEY", hint: "Optional — pipeline tracing." },
  { key: "serp_key", label: "SERP key", env: "SERP_API_KEY", hint: "Optional — paid discovery sources." },
];

export default function Settings() {
  const [account, setAccount] = useState<Account | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.getAccount().then(setAccount).catch((e) => setMsg(String(e)));
  }, []);

  if (!account) return <div className="text-slate-500">{msg || "Loading…"}</div>;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Settings</h2>
        <p className="text-sm text-slate-500">Local workspace · no login</p>
      </div>
      <div className="space-y-4">
        <h3 className="font-medium">Provider keys</h3>
        <p className="text-sm text-slate-500">
          Keys are read from your <code>.env</code> file. Set them there and restart the server
          to change them — there's nothing to save here.
        </p>
        {KEY_FIELDS.map((f) => {
          const set = Boolean(account.keys[f.key]);
          return (
            <div key={f.key} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
              <div>
                <div className="text-sm font-medium">{f.label}</div>
                <div className="text-xs text-slate-400">
                  <code>{f.env}</code> · {f.hint}
                </div>
              </div>
              <span className={`rounded-full px-2 py-0.5 text-xs ${set ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                {set ? `configured ${account.keys[f.key]}` : "not set"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
