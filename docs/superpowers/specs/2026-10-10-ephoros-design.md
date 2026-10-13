# Ephoros — Ephemeral Cloud & Kubernetes Resource Risk Detection

**Design spec** · 2026-10-10 · Status: draft for review

---

## 1. Purpose and success criteria

### 1.1 Problem

Cloud-native environments constantly create and destroy short-lived resources — CI/CD pods, spot VMs,
temporary IAM sessions, autoscaled containers. Daily inventory scans miss them, so crypto-mining
bursts, briefly exposed debug pods and stolen-session misuse go unnoticed. Ephoros discovers these
transient assets in near real time, detects risky behaviour, correlates detections into incidents,
scores them and produces analyst-ready narratives.

Source challenge: iamneo × Société Générale, *Ephemeral Cloud & Kubernetes Resource Risk Detection*
(https://societegenerale.iamneo.ai/ephemeral-cloud-kubernetes-resource-risk-detection/). This design
implements the challenge's **Option A (Advanced)** and exceeds it.

### 1.2 Audiences

1. **College minor project** — viva, report, clear methodology and architecture.
2. **Challenge submission** — deliverables checklist and measurable evaluation criteria.
3. **Portfolio** — production-grade engineering visible on GitHub.

### 1.3 Success criteria (measured by `just evaluate`, enforced in CI)

| Criterion (challenge) | Metric | Threshold |
|---|---|---|
| Ephemeral asset visibility | Recall of ephemeral class vs. ground truth | ≥ 0.95 |
| Detection latency | p95 of (alert pushed to UI − event observed) | ≤ 2 s |
| Noise reduction | 1 − (incidents ÷ raw detections) | ≥ 0.40 |
| Legit-burst suppression | Share of labelled legitimate bursts producing no incident | ≥ 0.90 |
| Incident correlation | Mean cluster purity | ≥ 0.85 |
| Risk scoring vs. analyst judgment | Spearman ρ (risk score vs. labelled severity) | ≥ 0.70 |
| Malicious detection quality | Precision / recall over malicious scenarios | ≥ 0.85 / ≥ 0.85 |
| Analyst readiness | Narrative citation validity | 100 % (invalid narratives are rejected) |
| Analyst readiness | MITRE technique match on 3 reference incidents | 3 / 3 |

Thresholds are initial targets; the first evaluation run may recalibrate them, recorded in an ADR.

---

## 2. Scope

### 2.1 In scope

- Labelled synthetic data generator + stream replay (cloud audit, Kubernetes, identity/session logs) in
  the challenge's proportions.
- Live ingestion from a local **kind** cluster (watch API + Kubernetes audit log).
- Normalization, enrichment, ephemeral/persistent classification.
- Three detection layers: YAML rules, statistical baselines, Isolation Forest.
- Graph-based incident correlation, explainable risk scoring.
- AI: incident narratives, investigation copilot, natural-language search, AI-suggested rules — via a
  pluggable LLM layer (Claude / Ollama, user-selectable).
- Angular dashboard with live updates; CSV export.
- Auth with Analyst and Admin roles.
- Docker Compose and Helm deployment; CI; evaluation harness; documentation deliverables.

### 2.2 Out of scope

- Ingesting real AWS/GCP/Azure accounts (the normalized schema keeps this possible later).
- Automated remediation (Ephoros never mutates monitored infrastructure).
- Multi-tenancy, SSO federation, SAML/SCIM.
- Public cloud hosting.

---

## 3. Architecture overview

```
                         ┌──────────────────────── Traefik (single origin, TLS) ────────────────────────┐
Browser ───────────────► │  /            → web   Angular 22 SPA (nginx-unprivileged)                     │
                         │  /api/auth/*  → auth  Hono + Better Auth (Node)  ── /api/auth/jwks            │
                         │  /api/v1/*    → api   FastAPI (REST + SSE)       ── verifies JWT via JWKS     │
                         └──────────────────────────────────────────────────────────────────────────────┘

 Sources                         Event bus                    Processing                    Storage
 ───────                         ─────────                    ──────────                    ───────
 simulator (CLI, labelled) ──┐
                             ├─► Redis Stream events.raw ─► worker (consumer group) ─────► Postgres
 k8s-watcher (kind:          │                                normalize → enrich →          schema auth (Better Auth)
   watch API + audit log) ───┘                                classify → detect(L1,L2,L3)   schema core (Ephoros)
                                                              → correlate → score
                                                              → narrate (async, LLM)
                                                                    │
                                                                    └─► Redis pub/sub ─► api /stream (SSE) ─► web

 LLM providers: Claude API · Ollama (local) · Template (no LLM) · Fake (tests)
```

### 3.1 Services

| Service | Tech | Role |
|---|---|---|
| `web` | Angular 22, Spartan/ui, Tailwind v4, ECharts, TanStack Query/Table | Dashboard SPA |
| `auth` | Hono on Node 22, Better Auth (JWT + admin plugins), Drizzle ORM | Users, sessions, roles, JWT issuance, JWKS |
| `api` | FastAPI, uvicorn | REST, SSE, AI endpoints |
| `worker` | Same Python image as `api` | Consumes Redis Streams, runs the pipeline |
| `k8s-watcher` | Same Python image | Watches kind; publishes raw events |
| `simulator` | Python CLI (uv package) | Generates labelled datasets, replays them |
| `postgres` | PostgreSQL 17 | Durable storage |
| `redis` | Redis 7 | Streams (event bus) + pub/sub (live alerts) |
| `traefik` | Traefik v3 | Reverse proxy / ingress |
| `ollama` | Ollama (optional profile) | Local LLM |

**Python is one codebase run as several processes** ("Option A"): a modular package with hexagonal
boundaries, one Docker image, separate entrypoints. Scales per process (multiple `worker` replicas),
avoids duplicated domain models.

---

## 4. Tooling and repository layout

### 4.1 Tool responsibilities

| Tool | Responsibility |
|---|---|
| **mise** | Pins every tool version (node, pnpm, python, uv, just, kubectl, kind, helm); loads `.env` |
| **uv** | Python deps, lockfile, venvs; uv **workspace** with multiple packages |
| **pnpm** | JS deps (Angular, Hono auth service, Nx) |
| **Nx** | Project graph, caching, `nx affected`; Python targets wrap `uv run …` via `nx:run-commands` |
| **just** | Single human entrypoint; each recipe is a one-line delegation (no logic) |

Rule: *just is the front door → Nx orchestrates → uv/pnpm manage packages → mise pins versions.*
Exact versions are pinned at scaffold time to current stable releases and recorded in `mise.toml`.

### 4.2 Repository layout

```
ephoros/
├─ mise.toml · justfile · nx.json · package.json · pnpm-workspace.yaml
├─ pyproject.toml                 # [tool.uv.workspace] members
├─ uv.lock · pnpm-lock.yaml · .env.example · compose.yaml
├─ apps/
│  ├─ web/                        # Angular shell: config, routes, layout
│  ├─ web-e2e/                    # Playwright
│  ├─ auth/                       # Hono + Better Auth
│  └─ api/                        # uv package `ephoros-api`
│     └─ src/ephoros_api/
│        ├─ api/v1/               # thin routers
│        ├─ services/             # use cases
│        ├─ domain/               # entities, ports (repositories, LLMProvider, EventBus)
│        ├─ adapters/             # db, redis, llm, k8s
│        └─ entrypoints/          # api.py, worker.py, k8s_watcher.py
├─ libs/
│  ├─ shared/api-contract/        # generated TS client (hey-api) from OpenAPI
│  ├─ web/
│  │  ├─ core/auth/               # Better Auth client, AuthStore, guards, interceptor
│  │  ├─ data-access/             # TanStack Query factories, StreamService (SSE)
│  │  ├─ ui/                      # Spartan helm components (owned)
│  │  ├─ ui-charts/               # ECharts wrappers
│  │  ├─ feature-overview/ · feature-inventory/ · feature-identities/
│  │  ├─ feature-incidents/ · feature-search/ · feature-rules/ · feature-admin/
│  │  └─ util/
│  └─ py/
│     ├─ detection-core/          # uv package: pipeline logic, framework-free
│     └─ simulator/               # uv package: generator + replay CLI
├─ rules/                         # built-in YAML detection rules
├─ models/                        # trained ML artifacts + metadata
├─ infra/
│  ├─ traefik/ · postgres/        # static config, init SQL
│  ├─ kind/                       # cluster config, audit policy
│  ├─ helm/ephoros/               # chart
│  └─ demo/                       # attack + CI-burst manifests
└─ docs/
   ├─ architecture.md · data-dictionary.md · detection-approach.md
   ├─ adr/ · incidents/ · evaluation/
   └─ superpowers/specs/ · superpowers/plans/
```

### 4.3 Module boundaries

Nx tags: `type:app|feature|data-access|ui|util|contract`, `scope:web|shared|py`.
Allowed: `feature → data-access | ui | util`; `data-access → contract | util`; `ui → util`.
Forbidden: `ui → data-access`, `feature → feature`. Enforced by `@nx/enforce-module-boundaries`.

Python: `import-linter` contracts — `domain` imports nothing from `adapters`, `api`, FastAPI or
SQLAlchemy; `detection-core` imports no web or DB framework.

### 4.4 justfile (indicative)

| Recipe | Delegates to |
|---|---|
| `setup` | `mise install`, `pnpm install`, `uv sync --all-packages` |
| `up [profile]` / `down` | `docker compose --profile … up -d` |
| `dev` | infra containers + `nx run-many -t serve -p web auth api worker` |
| `test` · `lint` · `typecheck` | `nx run-many -t …` |
| `e2e` | compose `e2e` profile + `nx e2e web-e2e` |
| `simulate n=3000` | `uv run --package simulator ephoros-sim generate --replay` |
| `train` | `uv run ephoros train` |
| `evaluate` | `uv run ephoros evaluate` |
| `gen-client` | `nx run api-contract:generate` |
| `migrate` | `uv run alembic upgrade head` + `pnpm --filter auth db:migrate` |
| `cluster-up` · `cluster-down` · `cluster-secrets` | kind + helm |
| `demo-attack` · `demo-ci-burst` · `demo-record` | kubectl apply demo manifests / Playwright recording |

---

## 5. Data model

### 5.1 Normalized event (OCSF-inspired)

All sources are mapped into one `Event` before detection.

| Field | Type | Notes |
|---|---|---|
| `event_id` | UUIDv7 | Time-sortable |
| `source` | enum | `cloud_audit`, `k8s`, `identity` |
| `category` | enum | `api_activity`, `resource_lifecycle`, `session`, `rbac` |
| `action` | string (enum-validated) | `create`, `delete`, `exec`, `assume_role`, `modify_sg`, `bind_role`, … |
| `outcome` | enum | `success`, `failure` |
| `observed_at` · `ingested_at` | timestamptz | Latency = processing time − `observed_at` |
| `actor` | object | `principal_id`, `principal_type` (`user`, `service_account`, `role`, `federated`), `session_id`, `source_ip`, `user_agent` |
| `resource` | object | `resource_uid`, `kind`, `name`, `namespace`, `account`, `region`, `labels`, `owner_ref` |
| `attributes` | JSONB | `privileged`, `host_network`, `image`, `command`, `exposed_ports`, `public_ip`, `sg_rules`, … |
| `raw` | JSONB | Original record (evidence) |

### 5.2 Core tables (schema `core`)

| Table | Purpose / key columns |
|---|---|
| `events` | Normalized events; BRIN index on `observed_at`; B-tree on `actor.principal_id`, `resource.resource_uid` |
| `event_labels` | Simulator ground truth (`event_id`, `scenario`, `is_malicious`, `severity`, `scenario_instance_id`). Read **only** by the evaluation harness |
| `assets` | `resource_uid`, `kind`, `first_seen`, `last_seen`, `deleted_at`, `ttl_seconds`, `lifecycle_class` (`ephemeral`/`persistent`/`unknown`), `class_confidence`, `class_reason`, owner chain. Rows retained after deletion (tombstones) |
| `identities` | `principal_id`, type, `federated_from`, baseline stats |
| `sessions` | `session_id`, principal, start/end, source IPs, geo |
| `detections` | `detector` (`rule:<id>`, `stat:<name>`, `ml:iforest`), `event_ids[]`, asset/identity refs, `severity`, `confidence`, `mitre[]`, `features` JSONB |
| `incidents` | `status` (`open`, `triaged`, `closed`, `false_positive`), `risk_score`, `score_breakdown` JSONB, window, graph snapshot, `triaged_by` (JWT `sub`) |
| `incident_detections` | Join table |
| `incident_narratives` | Versioned: provider, model, `prompt_version`, content JSONB, cited IDs, `validation_status` |
| `rules` | `rule_id`, `version`, YAML, `status` (`active`, `draft_ai`, `disabled`), `author`, backtest results |
| `copilot_messages` | Per-incident chat history |
| `analyst_feedback` | Verdicts used for score tuning |
| `llm_settings` | Per-task provider/model overrides (runtime) |
| `llm_calls` | Audit: task, provider, model, tokens, latency, cost, validation result |
| `eval_runs` | Metrics per evaluation run |

Storage: PostgreSQL 17, SQLAlchemy 2.0 async, Alembic migrations. TimescaleDB deliberately excluded
(volume is thousands of events; can be added later without schema rewrite). Better Auth owns schema
`auth` (Drizzle migrations); `core` references users only by JWT `sub`.

---

## 6. Data sources

### 6.1 Simulator (`libs/py/simulator`)

- Generates cloud audit (500–1000), Kubernetes (500–1000) and identity/session (200–500) events
  per run, from a **seed** (deterministic).
- Scenario mix (challenge): crypto-mining bursts 5–8 %, public exposure 3–5 %, unexpected identity
  activity 5–8 %, legitimate bursts 40–50 %, routine lifecycle 30–40 %.
- Encodes the challenge's ambiguity cases: CI pods vs attacker pods, autoscaler vs malicious bursts,
  automation vs stolen tokens, shared service-account tokens, federated identities, resources deleted
  before triage.
- Writes labels to `event_labels`; publishes events to `events.raw` either as fast as possible or at
  real-time pace (`--speed`).

### 6.2 Live Kubernetes (`k8s-watcher`)

- kind cluster created with an **audit policy** (Metadata level for most resources, RequestResponse for
  pods/exec/rolebindings) writing to a log file mounted to the host.
- Watcher combines: the watch API (pods, services, jobs, rolebindings — lifecycle) and the tailed audit
  log (who did it). Both mapped to `Event` and published to `events.raw`.
- Permissions: read-only ClusterRole (`get`, `list`, `watch`). Excludes namespace `ephoros-system`.

---

## 7. Detection pipeline (`libs/py/detection-core`)

Each stage is a small class with a single responsibility, unit-testable without infrastructure.

```
normalize → enrich → classify → detect (L1 ∥ L2 ∥ L3) → correlate → score → narrate (async)
```

- **Normalize** — source-specific mappers → `Event`; invalid records go to `events.dlq` stream with reason.
- **Enrich** — upsert asset/identity/session; resolve owner chain (pod → ReplicaSet → Deployment);
  resolve federated identity to originating principal; add time context (business hours, weekday).
- **Classify** — heuristics first (Job/CronJob owner, CI labels, spot/autoscaler markers, short session
  → ephemeral; StatefulSet/long-lived → persistent); unresolved cases go to a gradient-boosted
  classifier trained on simulator features (never labels at inference). Output: class, confidence,
  human-readable reason.
- **Detect**
  - **L1 rules** (YAML in `rules/`, versioned, JSON-Schema-validated): public exposure (LoadBalancer /
    NodePort / SG `0.0.0.0/0`), privileged pod without controller, `exec` into pod, off-hours or
    new-IP/geo session use, RBAC escalation (cluster-admin binding), miner image/command patterns.
    Each rule declares MITRE technique(s) (e.g. T1496, T1190, T1578, T1078, T1609, T1098).
  - **L2 statistical** — per-namespace and per-identity baselines over 5-minute windows; robust
    z-score / IQR on creation rate, API rate, distinct resource kinds. Bursts matching CI/autoscaler
    fingerprints are **suppressed** (recorded as suppressed, not discarded).
  - **L3 ML** — Isolation Forest over per-identity-window behaviour features.
- **Correlate** — NetworkX graph: nodes = identities, sessions, assets, IPs; edges = actions within a
  sliding window (default 15 min). Detections whose entities are connected inside the window merge into
  one incident; incidents update as new detections arrive.
- **Score**
  ```
  resource_risk = severity × exposure_window_factor × privilege_factor × confidence
  incident_risk = clamp(max(resource_risk) + breadth_bonus(#assets, #identities)
                        + layer_agreement_bonus(L1, L2, L3), 0, 100)
  ```
  Full breakdown stored in `score_breakdown`. Weights in config; tunable from `analyst_feedback`.
- **Narrate** — triggered for incidents above a configurable score threshold; runs asynchronously
  (separate stream `narratives.todo`) so LLM latency never blocks detection.

Latency instrumentation: every detection records `observed_at`, `detected_at`, `pushed_at`.

---

## 8. AI layer

### 8.1 Provider abstraction

Port `LLMProvider` (domain) with adapters: `ClaudeProvider`, `OllamaProvider`, `TemplateProvider`
(deterministic, no LLM), `FakeProvider` (recorded responses, tests/e2e). Operations:
`generate_structured(schema, messages)`, `chat_stream(messages, tools)`.

**User-selectable provider** (resolution order, highest first):
1. Runtime per-task setting in `llm_settings` (Admin UI; no restart).
2. Per-task env override, e.g. `LLM_TASK_COPILOT=ollama:<model>`.
3. Global env `LLM_PROVIDER=claude|ollama`, with `CLAUDE_MODEL`, `OLLAMA_MODEL`.

Tasks: `narrative`, `copilot`, `nl_search`, `rule_suggest`. Default when Claude is selected:
`claude-opus-5-5` for every task with per-task effort; cheaper models (Sonnet 5.5, Haiku 5.5) are
selectable per task in Admin settings. Full detail: `2026-10-10-ephoros-ai-layer-design.md`.

**Fallback:** on error/timeout/budget exhaustion the default fallback is `TemplateProvider` only (no
silent switch to another provider). `LLM_FALLBACK=ollama` opts in to provider fallback.

### 8.2 Features — "LLM proposes, code validates, human decides"

1. **Incident narrative** — input: evidence pack (incident, detections, top-N events trimmed, asset and
   identity context, score breakdown) as JSON. Output Pydantic model: `summary`, `timeline`,
   `likely_intent` + confidence, `mitre[]` (technique, justification, `evidence_event_ids`), `impact`,
   `remediation[]`, `open_questions[]`. Validation: every cited ID ∈ evidence pack; every technique ∈
   local ATT&CK allowlist. Fail → one retry → template.
2. **Copilot** — per incident; read-only tools `get_events`, `get_asset_history`,
   `get_identity_activity`, `find_similar_incidents`; max 8 tool calls per turn; streamed over SSE;
   answers cite event IDs.
3. **Natural-language search** — query → typed `EventFilter` (enum-restricted fields) → our query
   builder. The LLM never produces SQL. UI shows the parsed filter as editable chips.
4. **AI-suggested rules** — from an incident, draft YAML rule → JSON Schema validation → backtest over
   stored events (hits, label precision) → saved as `draft_ai` → Admin activates.

### 8.3 Classical ML

Gradient-boosted classifier (ephemeral/persistent) and Isolation Forest (scikit-learn). Trained via
`just train`; artifacts in `models/` with metadata (dataset hash, seed, metrics, date); loaded by the
worker at startup.

### 8.4 Guardrails

- Untrusted log content (labels, commands, user agents) wrapped in delimited data blocks; system prompt
  instructs data-only treatment; injection test cases in the suite.
- Secret/token/key redaction before any cloud LLM call.
- No write-capable tools; remediation is advisory text only.
- Daily token budget, per-user rate limit on AI endpoints, cache keyed on (incident version,
  prompt version).
- Every call audited in `llm_calls`, visible on the Admin page.

---

## 9. API and real-time

### 9.1 Layering

Routers (validation + auth only) → services (use cases) → domain (entities, ports) ← adapters.

### 9.2 Endpoints (`/api/v1`, cursor pagination)

| Area | Endpoints |
|---|---|
| Overview | `GET /overview/kpis`, `GET /overview/timeline?bucket=1m` |
| Assets | `GET /assets`, `GET /assets/{id}`, `GET /assets/ttl-histogram` |
| Identities | `GET /identities`, `GET /identities/{id}`, `GET /identities/{id}/sessions` |
| Events | `GET /events`, `POST /events/search/nl` |
| Incidents | `GET /incidents`, `GET /incidents/{id}`, `PATCH /incidents/{id}`, `POST /incidents/{id}/narrative:regenerate` |
| Copilot | `POST /incidents/{id}/copilot` (SSE response) |
| Rules | `GET/POST /rules`, `POST /rules/suggest`, `POST /rules/{id}:backtest`, `POST /rules/{id}:activate` (admin) |
| Export | `GET /export/detections.csv` (streamed) |
| Admin | `GET/PUT /admin/llm-settings`, `GET /admin/llm-calls`, `GET /admin/eval-runs` |
| Stream | `GET /stream` (SSE: `detection.created`, `incident.created`, `incident.updated`, `narrative.ready`) |
| Ops | `GET /healthz`, `GET /readyz`, `GET /metrics` |
| Test only | `POST /_test/scenario` — mounted only when `APP_ENV=e2e` |

### 9.3 Auth

- Better Auth (Hono, Node) with **JWT** plugin (exposes `/api/auth/jwks`) and **admin** plugin (roles
  `analyst`, `admin`; role included in JWT claims).
- Angular obtains a short-lived JWT (15 min) from Better Auth's token endpoint, refreshes it before
  expiry using the first-party session cookie (single origin via Traefik), and sends
  `Authorization: Bearer` on every API call. SSE streams (`/stream`, copilot) are consumed with a
  fetch-based SSE client (`@microsoft/fetch-event-source`) so they carry the same Bearer header —
  FastAPI has exactly one auth path (JWT), never a cookie path.
- FastAPI dependency `current_user`: PyJWT + `PyJWKClient` (cached, refreshed on unknown `kid`),
  verifies signature, `iss`, `aud`, `exp`, role. `require_role("admin")` guards admin routes.
- Traefik rate-limits `/api/auth/*`.

### 9.4 Cross-cutting

RFC 9457 problem+json errors with `trace_id`; `structlog` JSON logs; OpenTelemetry traces
(api → redis → worker); Prometheus metrics; `slowapi` rate limits on AI routes. OpenAPI →
`libs/shared/api-contract` via hey-api; CI fails on drift.

---

## 10. Frontend

- Angular 22: standalone components, zoneless, signals, new control flow, lazy routes, Signal Forms.
- Tailwind v4 + Spartan/ui (helm components owned in `libs/web/ui`); dark theme default, light toggle.
- Class merging: the [`cn`](https://github.com/shadcn-ui/cn) package (drop-in, zero-dependency
  replacement for `clsx` + `tailwind-merge`). After Spartan's CLI generates the helm utils, the generated
  `hlm()` helper is replaced by `export { cn, cn as hlm } from 'cn'`, so every generated component keeps
  working; `clsx` and `tailwind-merge` are removed from dependencies (aliased via pnpm `overrides` only if
  a Spartan package still imports them). Variant styling stays on `class-variance-authority`. VS Code
  Tailwind IntelliSense `classFunctions`: `["cn", "hlm", "cva"]`. Build-time compilation (`cn build`) is
  not used — the runtime package is already small and fast enough.
- Micro-interactions: ported from [interior.dev](https://www.interior.dev/)
  ([ddoemonn/interior](https://github.com/ddoemonn/interior), MIT). interior is React-only (React 19 +
  Motion + Tailwind v4, installed via the shadcn CLI), so selected components are **re-implemented as
  Angular standalone components/directives** in `libs/web/ui/src/interactions/`, animated with Motion's
  framework-agnostic `animate()` API (`motion` package). Division of labour: **Spartan brain** owns
  behaviour and accessibility; **interior** supplies the motion design. Where Spartan already has the
  component (dialog, sheet/drawer, popover, dropdown, tabs, tooltip, accordion, command, pagination,
  progress), Spartan stays and only interior's motion polish is borrowed. Every port honours
  `prefers-reduced-motion`, carries an MIT attribution header, and is listed in `THIRD_PARTY_NOTICES.md`.
  Components are ported when the feature that needs them is built, not up front.

  | interior component | Used for in Ephoros |
  |---|---|
  | Copy Button | Event IDs, resource UIDs, principals, remediation commands |
  | Hold to Confirm | Activate AI rule, mark incident false positive, reject rule (admin/destructive actions) |
  | Loading Button | Regenerate narrative, run backtest, run evaluation |
  | Segmented Control | Time range (15m/1h/24h/7d), lifecycle filter, theme toggle |
  | Tooltip Group | Dense icon toolbars, MITRE badges, severity chips |
  | Streaming Text | Copilot streamed answers |
  | Typing Indicator | Copilot waiting / model thinking |
  | Task Steps | Copilot tool activity; rule pipeline (draft → validate → backtest) |
  | Value Flash | KPI tiles updating from SSE |
  | New Items Pill | "3 new incidents" pill on live lists instead of the list jumping |
  | Live Activity | Live detection feed on Overview |
  | Skeleton Swap | Loading → content transitions |
  | Inline Validation · Password Strength · Floating Label | Login/sign-up, rule editor, admin settings forms |
  | Tag Input | Editable NL-search filter chips, rule MITRE tags |
  | Expanding Search | Top-bar NL search entry |
  | Tree View | Asset owner chain (Deployment → ReplicaSet → Pod) |
  | Scroll Spy | Incident detail section nav (Summary · Timeline · Graph · Evidence · Narrative) |
  | Sortable Table (motion only) | Row re-order animation on TanStack Table sorting |
  | Progress Bar | Evaluation / training runs |

  Not used (no fit): like burst, logo marquee, swipe deck, lightbox, snap carousel, OTP input, poll
  results, presence avatars, wizard steps, reorder list, filter grid.
- Server state: TanStack Query (Angular adapter). UI state: signals; filters synced to URL. No NgRx.
- Tables: TanStack Table. Charts: ECharts via `ngx-echarts` (TanStack Charts is React-only).
- `StreamService` consumes SSE and invalidates affected queries.
- Pages: Overview (KPIs, spike timeline with suppressed bursts shaded, live feed); Inventory (asset
  table, TTL histogram, class split); Identities (risky identities, sessions, off-hours heatmap);
  Incidents (list → detail: risk breakdown, entity graph, timeline, evidence, AI narrative with
  clickable citations, copilot panel, triage); Search (NL → chips → results → CSV); Rules (YAML editor
  with CodeMirror 6, suggest → backtest → approve); Admin (LLM settings per task, LLM call log,
  evaluation runs). Command palette (⌘K).
- Accessibility: keyboard navigation, ARIA via Spartan brain, colour-blind-safe severity palette.

---

## 11. Infrastructure and deployment

### 11.1 Docker Compose

Services: `traefik`, `web`, `auth`, `api`, `worker`, `postgres`, `redis`; profiles `live`
(`k8s-watcher`), `ollama`, `obs` (Prometheus + Grafana), `e2e` (isolated DB/Redis, `LLM_PROVIDER=fake`,
`APP_ENV=e2e`). TLS locally via mkcert.

### 11.2 kind + Helm

- `infra/kind/cluster.yaml` with audit policy; Traefik installed as ingress.
- Chart `infra/helm/ephoros`: Deployments (web, auth, api, worker ×N, watcher ×1), Traefik
  IngressRoutes, Postgres/Redis StatefulSets (dev values), ConfigMaps, Secret (from
  `just cluster-secrets`).
- Hardening: non-root, read-only root FS, dropped capabilities, resource requests/limits,
  NetworkPolicies, probes. Ephoros's own deployment passes its own detection rules.

### 11.3 Demo scenarios (`infra/demo/`, harmless)

- `demo-attack`: stolen SA token creates privileged, controller-less pod with miner-like name/command
  (busybox loop, no real mining) → NodePort exposure → `exec` → cluster-admin RoleBinding → self-delete
  after ~90 s.
- `demo-ci-burst`: legitimate Job burst labelled as CI — expected to be suppressed.

### 11.4 Images and config

Multi-stage, non-root images: Python (`uv sync --frozen --no-dev`, slim), web (Node build → nginx
unprivileged), auth (Node build → node slim). Tagged by git SHA; pushed to GHCR from `main`.
`.env.example` committed, `.env` git-ignored, loaded by mise.

---

## 12. Testing

| Level | Tooling | Scope |
|---|---|---|
| detection-core unit | pytest + Hypothesis | Rules, baselines, classifier heuristics, scoring, correlation; coverage ≥ 90 % |
| API integration | pytest + httpx + Testcontainers | Endpoints, auth (test JWKS), SSE, CSV |
| Pipeline e2e | pytest | Simulator → Redis → worker → DB assertions |
| LLM layer | pytest + `FakeProvider` | Citation/MITRE validation, fallback, injection, redaction; no real LLM in CI |
| Auth service | Vitest | Config, JWT claims, JWKS, roles |
| Angular | Vitest | Components, query factories, guards, SSE invalidation |
| Browser e2e | Playwright | See §12.1 |
| Architecture | Nx boundaries + import-linter | Layering rules |

### 12.1 Playwright (`apps/web-e2e`, `@nx/playwright`)

- Specs: auth, overview, live-stream (inject scenario → incident appears without reload), incident
  detail (citation jumps, triage), copilot (streamed answer), search (NL → chips → CSV), rules
  (suggest → backtest → approve), admin (switch provider per task), a11y.
- Determinism: compose `e2e` profile with isolated stores; fixed-seed dataset; `FakeProvider`;
  `global-setup` logs in per role via Better Auth and stores `storageState`; role/label locators first,
  `data-testid` second; web-first assertions and `expect.poll`, no sleeps.
- Quality gates: `@axe-core/playwright` (fail on serious/critical); `toHaveScreenshot()` for overview
  and incident detail in dark/light with masked dynamic regions.
- Browsers: Chromium, Firefox, WebKit + one tablet viewport.
- CI: sharded; traces, videos, screenshots and HTML report uploaded on failure.
- `just demo-record`: scripted Playwright walkthrough recorded to video for viva/submission/portfolio.

## 13. Evaluation harness

`just evaluate --seed <n>`: generate labelled dataset → replay through the real pipeline → compute §1.3
metrics → write `docs/evaluation/report.md` and an `eval_runs` row. Includes an **ablation** table
(L1 only; L1+L2; L1+L2+L3). CI runs it with a fixed seed and fails on threshold regression.

## 14. CI/CD (GitHub Actions)

- Setup via mise; pnpm and uv caches.
- `nx affected -t lint typecheck test build` (Python + TS).
- OpenAPI client drift check.
- `just evaluate` with thresholds.
- Playwright e2e (sharded) on affected PRs.
- Security: `pip-audit`, `pnpm audit`, Trivy image scan, gitleaks.
- `main`: build/push images to GHCR; `helm lint` + `helm template`.
- Conventional Commits (commitlint) and lefthook pre-commit (Ruff, Prettier, ESLint on staged files).

## 15. Documentation deliverables

README (one-command quick start), `docs/architecture.md` (diagram: ingest → enrich → detect →
cluster → score → LLM narrative → dashboard), `docs/data-dictionary.md`,
`docs/detection-approach.md`, ADRs (`docs/adr/`), three sample incidents with evidence, MITRE
mapping and guardrails (`docs/incidents/`), evaluation report. Framework mapping: NIST SP 800-53
CM-8, SI-4, IR-4; MITRE ATT&CK; CIS Kubernetes and cloud benchmarks.

## 16. Error handling and resilience

- Invalid raw events → `events.dlq` with reason; visible in Admin.
- Worker uses Redis consumer groups with explicit ACK; pending entries are reclaimed after a timeout
  (`XAUTOCLAIM`); processing is idempotent on `event_id`.
- LLM failures degrade to the template narrative; detection never depends on the LLM.
- JWKS fetch failure: cached keys used; unknown `kid` triggers one refresh, otherwise 401.
- SSE clients reconnect with `Last-Event-ID`; missed events recovered by query refetch.
- Readiness probes fail when Postgres or Redis is unreachable.

## 17. Milestones

Each milestone ends with a working, demoable system and gets its own implementation plan.

1. **Foundation** — mise/uv/pnpm/Nx/just workspace; Compose with Traefik, Postgres, Redis; CI skeleton;
   OpenAPI codegen.
2. **Auth** — Hono + Better Auth (JWT, admin); FastAPI JWKS verification; Angular login, guards.
3. **Data** — simulator; normalized schema; Redis ingest; worker skeleton; event storage.
4. **Detection v1** — enrich, classify, L1 rules, scoring, incidents; evaluation harness v1.
5. **Dashboard v1** — overview, inventory, identities, incidents; SSE live updates; CSV export.
6. **Advanced detection** — L2 statistics + suppression; L3 Isolation Forest; graph correlation;
   ablation.
7. **AI** — provider layer + settings UI; narratives; copilot; NL search; AI-suggested rules.
8. **Live Kubernetes** — kind + audit log; watcher; Helm chart; demo scenarios.
9. **Polish** — observability profile; Playwright suite completion and demo recording; docs;
   sample incidents; final evaluation report.

## 18. Key decisions (to be recorded as ADRs)

| Decision | Choice | Rejected alternatives |
|---|---|---|
| Python service shape | One codebase, multiple processes | Microservice per stage; single process |
| Event bus | Redis Streams | Kafka/Redpanda, NATS, in-process queues |
| Auth | Better Auth on Hono (Node); FastAPI as JWT resource server | Express, Elysia (Bun-only), fastapi-users (maintenance mode), AuthX, Keycloak |
| Reverse proxy | Traefik | Caddy, nginx |
| UI kit | Spartan/ui + Tailwind | Angular Material, PrimeNG, Taiga |
| Charts | ECharts | TanStack Charts (React-only), Chart.js |
| Tailwind class merging | `cn` | `clsx` + `tailwind-merge` (Spartan default) |
| Micro-interactions | interior.dev designs ported to Angular + Motion `animate()` | Installing interior directly (React-only); Angular animations only |
| Real-time transport | SSE | WebSockets |
| DB | Postgres 17, no TimescaleDB | TimescaleDB, SQLite |
| LLM | Pluggable, user-selected (Claude / Ollama), template fallback | Single hard-wired provider |
| E2E testing | Playwright | Cypress, WebdriverIO |
| Tooling | mise + uv + pnpm + Nx + just | Per-tool version managers, Makefile |
