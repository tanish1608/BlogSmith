# BlogSmith — A Production-Grade Agentic Blogging Service

**One authenticated server that researches, writes, illustrates, and distributes
human-like, SEO-strong blog posts for all of your websites — with a non-negotiable
human-expert checkpoint.**

| | |
|---|---|
| **Swagger / API** | `http://localhost:8000/docs` |
| **Dashboard** | `http://localhost:8000/` |

---

## Abstract

BlogSmith is a multi-tenant content engine behind a single API + dashboard. A user
authenticates (Firebase Auth), stores their own **Gemini API key** and **custom prompts**
per website, and sets a cadence (e.g. *10 blogs, 9am daily*). For each blog, a **9-stage
LangGraph agent pipeline** discovers a buyer-intent topic, researches it against primary
sources, outlines it to search intent, drafts it in the site's brand voice, edits it,
**emails the draft for a human expert pass**, then finalizes SEO metadata, **generates
images with Gemini** (graphs/flowcharts/photos), and repurposes the post into a LinkedIn
thread. Every stage degrades gracefully when an optional integration is missing, and the
whole thing runs locally with zero cloud infrastructure.

---

## Highlights

- **9-stage LangGraph pipeline** — `Discovery → Research → Outline → Draft → Critique →
  [human email gate] → Finalize → Visuals → Distribute`, one clean LangSmith trace per blog.
- **Human-expert email gate** — each draft is emailed with signed **approve / edit / reject**
  links. The run pauses durably (the Firestore document is the checkpoint) and resumes in a
  separate serverless process when a link is clicked. No inbound mail parsing.
- **The prompts are the product** — authored, versioned default system prompts for every
  stage (anti-AI-tell writing rules, SEO checklist, source discipline) that each user layers
  their own **per-domain custom prompts** and brand voice on top of.
- **Gemini image generation** — the Visuals stage renders each planned image and embeds it
  with alt text; diagrams fall back to **Mermaid** when image generation is unavailable.
- **BYOK, encrypted** — users bring their own Gemini (and optional LangSmith/SERP/SendGrid)
  keys; everything is encrypted at rest (Fernet) and never enters the graph checkpoint.
- **Heuristic-first, degrades gracefully** — no SERP key → autocomplete discovery; no
  LangSmith → no tracing; no image key → Mermaid; SEO score is fully deterministic. The
  writer (Gemini) is the only hard dependency, and it fails *loudly*, never with an empty post.
- **Scheduling that scales** — one Cloud Scheduler cron hits `/scheduler/tick`, which fans
  out due cadences across all sites; no per-user cron sprawl.
- **Local-first** — runs entirely against the Firebase emulator (or the in-memory test fake);
  the React dashboard is served by FastAPI.

---

## Tech stack

| Layer | Technology |
|---|---|
| **API** | FastAPI + Pydantic v2 — auto Swagger at `/docs` |
| **Agent orchestration** | LangGraph state graph (`discovery → … → distribute`) |
| **LLM** | Google Gemini via `langchain-google-genai` (pluggable) |
| **Images** | Gemini image generation via `google-genai`; Mermaid fallback |
| **Observability** | LangSmith — one trace per blog |
| **Auth + DB** | Firebase Auth + Firestore (central project) |
| **Image storage** | Firebase Storage |
| **Secrets** | Fernet-encrypted BYOK keys in Firestore; Secret Manager in prod |
| **Dashboard** | React 18 + Vite + Tailwind, served by FastAPI |
| **Hosting** | Cloud Run Service (API) + Cloud Run Job (run executor) + Cloud Scheduler |

---

## Architecture

```mermaid
flowchart TD
    USER(["👤 Dashboard / API client"])
    subgraph SVC["☁️ Cloud Run Service"]
      API["FastAPI + Dashboard + Swagger\naccount · sites · runs · approvals · scheduler"]
    end
    subgraph JOB["☁️ Cloud Run Job (one per run)"]
      GRAPH["LangGraph pipeline\ndiscovery → … → critique → gate"]
    end
    DB[("🔥 Firestore\nusers · sites · runs (stage slices)")]
    STORE[("🖼️ Storage\ngenerated images")]
    LS["🔍 LangSmith\n1 trace per blog"]
    MAIL["✉️ Approval email\napprove / edit / reject links"]

    USER -->|HTTPS + ID token| API
    API -->|dispatch Phase A| JOB
    GRAPH -->|write slices| DB
    GRAPH -->|pause + send| MAIL
    MAIL -->|signed link| API
    API -->|Phase B: finalize→visuals→distribute| DB
    GRAPH --> STORE
    GRAPH -. trace .-> LS
    API -->|read| DB
```

The human gate splits execution into **Phase A** (discovery → gate, in the Job) and
**Phase B** (finalize → visuals → distribute, resumed in the Service on link click). The same
compiled graph serves both via a conditional entry point; state is rebuilt from the run
document, so a paused run survives any process restart.

---

## The pipeline

1. **Discovery** — ranks topic candidates (seed topics + Google autocomplete by default;
   GSC/SERP adapters behind the same interface) by buyer intent.
2. **Research** — gathers facts with a primary-source bias for regulatory topics; separates
   verified from unverified claims.
3. **Outline** — structures to search intent + the site's pillar/cluster map; plans internal
   links, visual placements, and the expert-insight slot.
4. **Draft** — writes the full Markdown in brand voice, weaving in the expert insight and
   emitting `[[IMAGE: …]]` placeholders. *(Requires a Gemini key.)*
5. **Critique** — a ruthless editor pass: strips fluff, kills AI tells, flags claims, runs the
   SEO checklist. Deterministic SEO score from `seo.py`; the model only narrates.
6. **Human email gate** — emails the draft with approve/edit/reject links; pauses the run.
7. **Finalize** — title, meta description, slug, JSON-LD schema, per-image generation prompts
   and alt text. The body is locked.
8. **Visuals** — generates each image with Gemini → Firebase Storage → embeds it; diagrams
   fall back to Mermaid, photos drop cleanly on failure.
9. **Distribute** — repurposes the post into a LinkedIn thread.

---

## Run it yourself (local, zero cloud infra)

```bash
# Backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # add a Gemini key to generate real content/images

# Build the dashboard (served by FastAPI)
cd frontend && npm install && npm run build && cd ..

# Firebase emulator (needs Java 21) — optional; tests use an in-memory fake instead
firebase emulators:start &

uvicorn blogsmith.api.main:app --reload
#   → http://localhost:8000        (dashboard)
#   → http://localhost:8000/docs   (Swagger)

# Full pipeline end-to-end (uses fakes if no Gemini key is set):
python scripts/demo_run.py --topic "DPDPA compliance checklist for SaaS"

# Correctness gates
ruff check blogsmith tests
pytest -q
```

With `AUTH_DISABLED=true` (the default in `.env.example`), the API skips Firebase token
verification and uses a fixed dev user — so the dashboard and Swagger work with no login.

---

## Repository map

```
blogsmith/
  api/
    main.py            app factory, lifespan → Firebase init, serves dashboard + /docs
    auth.py            Firebase ID-token dependency (AUTH_DISABLED for dev)
    jobs.py            dispatch: Cloud Run Job (prod) | background task (dev)
    routers/
      account.py       BYOK provider keys (encrypted)
      sites.py         CRUD sites + per-site custom prompts + schedule
      runs.py          create run, status, result
      approvals.py     email-gate landing pages (approve/edit/reject)
      scheduler.py     POST /scheduler/tick (Cloud Scheduler)
      tools.py         /health, /tools/discover, /tools/draft, /tools/preview-image
  graph/               THE INTELLIGENCE LAYER
    blog_graph.py      StateGraph wiring + run/resume (conditional entry; gate)
    nodes.py           9 stage nodes (persist slice + advance status)
    state.py           channel-typed BlogState (no secrets)
    context.py         RunContext — live deps + Firestore persistence
    model.py           LlmClient + LlmBudget (graceful degradation)
    image_model.py     Gemini image gen + Mermaid fallback
    checkpoint.py      Firestore-as-checkpoint (state ↔ run doc)
  prompts/
    defaults.py        authored system prompts per stage + human-like rules + SEO checklist
    assemble.py        base + brand voice + per-site custom prompt layering (versioned)
  discovery.py research.py outline.py draft.py critique.py finalize.py visuals.py distribute.py
  seo.py               deterministic SEO scoring
  email_gate.py        signed approval tokens + email sender (SendGrid | console)
  schedule.py          cadence → due-slot computation
  runner.py            build RunContext from Firestore; execute_run / execute_resume
  run_job.py           Cloud Run Job entrypoint
  firestore_db.py storage.py crypto.py accounts.py config.py models.py schemas.py markdown_utils.py

frontend/              React + Vite + Tailwind dashboard (settings, sites, runs, results)
deploy/                cloudbuild yamls, Firestore/Storage rules, GCP setup guide
scripts/               demo_run.py, export_openapi.py
tests/                 in-memory Firestore fake + per-stage / pipeline / gate-resume tests
```

---

## Security notes

- Provider keys are Fernet-encrypted at rest and decrypted only into the in-memory run
  context — never persisted into the graph state/checkpoint.
- Email approval links are short-lived signed JWTs; the action is bound into the token.
- Firestore/Storage rules deny direct client writes; all writes go through the Admin SDK,
  which enforces per-uid ownership.
