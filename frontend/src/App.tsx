import { useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import { firebaseEnabled, signIn, signOut, watchAuth } from "./auth";
import Settings from "./components/Settings";
import SiteDetail from "./components/SiteDetail";
import type { Site } from "./types";

export default function App() {
  const [authed, setAuthed] = useState(!firebaseEnabled);
  const [tab, setTab] = useState<"sites" | "settings">("sites");

  useEffect(() => watchAuth((user) => setAuthed(!firebaseEnabled || !!user)), []);

  if (!authed) return <Login onDone={() => setAuthed(true)} />;

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b bg-white px-6 py-3">
        <div className="flex items-center gap-6">
          <span className="text-lg font-bold">BlogSmith</span>
          <nav className="flex gap-1">
            <TabButton active={tab === "sites"} onClick={() => setTab("sites")}>Sites</TabButton>
            <TabButton active={tab === "settings"} onClick={() => setTab("settings")}>Settings</TabButton>
          </nav>
        </div>
        {firebaseEnabled && (
          <button onClick={() => signOut()} className="text-sm text-slate-500">Sign out</button>
        )}
      </header>
      <main className="mx-auto max-w-5xl px-6 py-6">
        {tab === "settings" ? <Settings /> : <SitesTab />}
      </main>
    </div>
  );
}

function SitesTab() {
  const [sites, setSites] = useState<Site[]>([]);
  const [selected, setSelected] = useState<Site | null>(null);
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [msg, setMsg] = useState("");

  async function refresh() {
    try {
      setSites(await api.listSites());
    } catch (e) {
      setMsg(String(e));
    }
  }
  useEffect(() => { refresh(); }, []);

  async function create() {
    if (!name || !domain) return;
    try {
      const s = await api.createSite({ name, domain });
      setName(""); setDomain("");
      await refresh();
      setSelected(s);
    } catch (e) {
      setMsg(String(e));
    }
  }

  return (
    <div className="grid grid-cols-[260px_1fr] gap-6">
      <aside className="space-y-3">
        <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-2">
          <h3 className="text-sm font-medium">New site</h3>
          <input className="inp" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="inp" placeholder="domain.com" value={domain} onChange={(e) => setDomain(e.target.value)} />
          <button onClick={create} className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm text-white">Add site</button>
        </div>
        <ul className="rounded-xl border border-slate-200 bg-white divide-y">
          {sites.map((s) => (
            <li key={s.id}>
              <button onClick={() => setSelected(s)}
                className={`w-full px-3 py-2 text-left text-sm ${selected?.id === s.id ? "bg-slate-100 font-medium" : ""}`}>
                {s.name}
                <span className="block text-xs text-slate-400">{s.domain}</span>
              </button>
            </li>
          ))}
          {sites.length === 0 && <li className="px-3 py-3 text-sm text-slate-400">No sites yet.</li>}
        </ul>
        {msg && <p className="text-xs text-red-600">{msg}</p>}
      </aside>
      <section>
        {selected ? (
          <SiteDetail
            site={selected}
            onSaved={(s) => { setSelected(s); refresh(); }}
            onDeleted={() => { setSelected(null); refresh(); }}
          />
        ) : (
          <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-slate-400">
            Select a site, or create one to start generating blogs.
          </div>
        )}
      </section>
    </div>
  );
}

function Login({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  async function submit() {
    try {
      await signIn(email, password);
      onDone();
    } catch (e) {
      setErr(String(e));
    }
  }
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-80 space-y-3 rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-lg font-bold">BlogSmith</h1>
        <input className="inp" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="inp" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button onClick={submit} className="w-full rounded-lg bg-blue-600 px-3 py-2 text-white">Sign in</button>
        {err && <p className="text-xs text-red-600">{err}</p>}
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-sm ${active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
      {children}
    </button>
  );
}
