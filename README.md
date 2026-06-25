# BlogSmith — A Local Agentic Blogging Service

**One local dashboard that researches, writes, illustrates, and distributes
human-like, SEO-strong blog posts for all of your websites — with a human-expert
review gate, shown as a live LangSmith-style run thread.**

Runs entirely on your machine: a **SQLite** database, a local **media** folder for
images, API keys from **`.env`**. No cloud, no auth, no Firebase.

| | |
|---|---|
| **Dashboard** | `http://localhost:5173` (dev) · `http://localhost:8000` (served by the API) |
| **Swagger** | `http://localhost:8000/docs` |

---

## Highlights

- **9-stage LangGraph pipeline** — `Discovery → Research → Outline → Draft → Critique →
  [review gate] → Finalize → Visuals → Distribute`, one clean LangSmith trace per blog.
- **LangSmith-style run thread** — each blog is a live vertical timeline: which stage is
  running, each stage's output expandable, with the review gate inline.
- **In-dashboard review gate** — the run pauses (the SQLite row is the durable checkpoint)
  and shows **approve / edit / reject**; approve/edit resumes finalize → visuals → distribute.
- **MDX output** — finished posts download as `.mdx` with YAML frontmatter (title,
  description, dates, author, tags, type) ready for your site.
- **The prompts are the product** — authored default system prompts per stage that each
  site layers its own per-domain custom prompts and brand voice on top of.
- **CSV in/out** — download/edit/upload a site's config as CSV (name + domain locked), and
  bulk-queue many topics from one CSV (staged — nothing runs until you click *Generate*).
- **Concurrent runs** — blogs execute in parallel (capped by `MAX_CONCURRENT_RUNS`), and each
  run's images generate concurrently. Cancel any run mid-flight; approve/download/publish a
  run right from its card.
- **One-click publish** — push a finished `.mdx` to your site's Field Notes API (enable with
  `PUBLISH_ENABLED` + `FIELD_NOTES_TOKEN`; see `docs/field-notes-api.md`).
- **Gemini image generation** — the Visuals stage renders each planned image into the local
  media folder; diagrams fall back to **Mermaid** when image generation is unavailable.
- **Local scheduler** — an in-process scheduler fires due cadences (e.g. *10 blogs, 9am daily*)
  while the app runs.
- **Heuristic-first, degrades gracefully** — no SERP key → autocomplete discovery; no LangSmith
  → no tracing; no image key → Mermaid; SEO score is deterministic. Gemini (text) is the only
  hard dependency.

---

## Tech stack

| Layer | Technology |
|---|---|
| **API** | FastAPI + Pydantic v2 — auto Swagger at `/docs` |
| **Agent orchestration** | LangGraph state graph |
| **LLM** | Google Gemini via `langchain-google-genai` (pluggable) |
| **Images** | Gemini image generation via `google-genai`; Mermaid fallback; saved to a local folder |
| **Observability** | LangSmith — one trace per blog (optional) |
| **Database** | SQLite (one local file) |
| **Dashboard** | React 18 + Vite + Tailwind, served by FastAPI |

---

## Run it locally

**One-time setup**

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your GEMINI_API_KEY

cd frontend && npm install && cd ..
```

**Run both servers (one command)**

```bash
./dev.sh
#   → http://localhost:5173   dashboard (Vite dev server, hot reload)
#   → http://localhost:8000   API + Swagger at /docs
```

That's it — no login. The first run creates `blogsmith.db` and a `media/` folder.

**Other commands**

```bash
# Full pipeline end-to-end without a server (fakes if no Gemini key is set):
python scripts/demo_run.py --topic "DPDPA compliance checklist for SaaS"

# Correctness gates
ruff check blogsmith tests
pytest -q
```

---

## The pipeline

1. **Discovery** — ranks topic candidates by buyer intent (seed topics + autocomplete).
2. **Research** — gathers facts with a primary-source bias; separates verified from unverified.
3. **Outline** — structures to search intent + the site's pillar/cluster map; requires a real
   conclusion section.
4. **Draft** — writes the full Markdown in brand voice, with `[[IMAGE: …]]` placeholders.
   *(Requires a Gemini key.)*
5. **Critique** — strips fluff, kills AI tells, flags claims, runs the SEO checklist.
6. **Review gate** — pauses the run; you approve/edit/reject in the dashboard thread.
7. **Finalize** — title, meta, slug, tags, type, JSON-LD (real dates + site author), image prompts.
8. **Visuals** — generates each image with Gemini → local media folder → embeds it; Mermaid fallback.
9. **Distribute** — repurposes the post into a LinkedIn thread.

---

## Repository map

```
blogsmith/
  api/
    main.py            app factory; init SQLite, mount /media, start scheduler, serve dashboard
    jobs.py            in-process run dispatch (background tasks)
    routers/
      account.py       env key status (read-only)
      sites.py         CRUD sites + per-site custom prompts + schedule + config CSV
      runs.py          create run, status, result (.mdx), review decision, bulk-topics CSV
      scheduler.py     POST /scheduler/tick (manual trigger)
      tools.py         /health, /tools/discover, /tools/draft, /tools/preview-image
  graph/               THE INTELLIGENCE LAYER
    blog_graph.py      StateGraph wiring + run/resume (conditional entry; gate)
    nodes.py           9 stage nodes
    state.py context.py model.py image_model.py checkpoint.py
  prompts/             authored default system prompts per stage + assembly
  discovery.py research.py outline.py draft.py critique.py finalize.py visuals.py distribute.py
  store.py             SQLite persistence (sites/runs)
  storage.py           local image storage
  accounts.py          API keys from .env
  scheduler_local.py   in-process cadence scheduler
  seo.py schedule.py runner.py csv_io.py mdx.py markdown_utils.py config.py models.py schemas.py

frontend/              React + Vite + Tailwind dashboard (no login)
scripts/               demo_run.py, export_openapi.py
tests/                 SQLite-backed per-stage / pipeline / gate-resume / CSV tests
```

---

## Notes

- **Single local workspace, no auth** — anyone with access to the machine has access. Don't
  expose the port publicly without putting your own auth in front.
- **Keys live in `.env`** — `GEMINI_API_KEY` (required), `LANGSMITH_API_KEY` / `SERP_API_KEY`
  (optional). Change them and restart the server.
