# M4 Detection v1: design

Status: draft for review · 2026-10-29 · builds on the main spec (`2026-10-10-ephoros-design.md`
§1.3, §5.2, §7, §13) and the code as of `0e7e4c4`. Where this document and the main spec differ,
this document wins for M4.

Marking: **(decided)** = the project owner said so. **(builder's call)** = chosen while writing this
design; the owner may override it.

## 1. Intent

M4 turns stored events into incidents and **proves, with numbers, that detection works**. The
evidence is the evaluation report. The goal is a reliable detection pipeline, not a passing
report (decided).

Priority order (decided):

1. `just evaluate`: replays a labelled dataset through the real pipeline and writes a report
   comparing every §1.3 metric with its target.
2. Basic incident inspection through the API: score, score breakdown, the rules that fired, and
   evidence.
3. The dashboard is **M5**. Nothing from M5 or M6 is pulled in (decided).

## 2. Goals

- **Pipeline stages:** enrich → classify (heuristics) → L1 rules → correlate (simple) → score.
  They run inside the existing worker, on the same Redis stream and database as live traffic.
- **Simulator coverage:** labelled scenarios cover every M4 rule. Two attacks are new: exec into a
  pod and a cluster-admin binding. Each new attack also gets a legitimate look-alike (decided).
- **Asset-class ground truth:** the simulator records, on the label side only, whether each asset
  is ephemeral or persistent (decided).
- **`just evaluate`:**
  - reproducible from a fixed seed
  - every metric computed from what the pipeline actually wrote
  - a held-out seed for the headline report
  - every run recorded
  - CI states per metric: pass / fail / not yet measured (decided)
- **Incident API:** `GET /api/v1/incidents` and `GET /api/v1/incidents/{id}` behind the existing
  JWT auth, added to the generated TypeScript client (decided).

## 3. Non-goals (later milestones)

| Not in M4                                                           | Where                                                   |
| ------------------------------------------------------------------- | ------------------------------------------------------- |
| L2 statistical baselines and burst suppression, L3 Isolation Forest | M6                                                      |
| NetworkX graph correlation                                          | M6                                                      |
| Gradient-boosted classifier fallback                                | M6 (builder's call: M4 classifies with heuristics only) |
| Dashboard pages, SSE `/stream`, `PATCH /incidents/{id}` triage      | M5                                                      |
| Narratives, copilot, AI-suggested rules, `rules` table              | M7                                                      |
| `sessions` table, identity pages                                    | M5 (only if the pages need it)                          |

## 4. Anti-goals (a failure even if it technically works)

These are decided:

- Detection reads labels, directly or indirectly, or depends on a simulator artifact rather than
  behaviour.
- A metric is hard-coded, assumed, or computed from anything other than the pipeline's stored
  output.
- A target is weakened or the dataset is edited to make a number pass.
- Precision goes up only because recall went down. Precision and recall are always reported
  together.
- Tuning is done on the held-out seed.

## 5. Constraints from the existing code

- **Framework-free core.** Detection logic lives in `libs/py/detection-core` (`ephoros_detection`),
  which import-linter keeps free of fastapi, sqlalchemy, redis and asyncpg. Persistence goes
  through ports in `ephoros_api.domain` and adapters in `ephoros_api.adapters`, following the
  existing `EventStore` / `IngestService` pattern.
- **Labels never on the stream.** `core.event_labels` is written by the simulator and read only by
  the evaluation harness. The stream envelope is `{event_id, source, raw}`.
- **The no-giveaway test.** `test_no_single_field_gives_the_label_away`: no user agent or source
  /24 seen in malicious events may be missing from benign ones. New scenarios must keep it green.
- **Golden digest.** `test_golden_digest_seed_7` pins the dataset. Adding scenarios changes the
  digest; update it in the same commit that changes the generator, with the reason in the commit
  message.
- **Volumes and mix.** Event volume per source and the scenario mix ranges (`EVENTS_PER_SOURCE`,
  `MIX`) are challenge proportions. New scenarios must fit inside them; adjust shares only within
  the challenge's stated ranges.
- **Process.** Python 3.13, mypy strict, Ruff (with FAST), FastAPI skill conventions (Annotated
  dependency aliases, return types, router-level auth). Exact version pins.

## 6. Design

### 6.1 Where detection runs

Detection runs in the **worker**, right after normalization, on the events that batch newly
inserted (builder's call). Storing events and every detection write for that batch happen in
**one database transaction**. If the worker dies mid-batch, nothing is half-done: the batch is
redelivered, and events already stored were already fully detected, so they are skipped. This
keeps the existing idempotency guarantee.

- **No wall clock.** Every time-based decision (windows, first-seen, lifetimes) uses the event's
  `observed_at`, never the wall clock, so replaying history gives the same result as live
  traffic.
- **Batch-independent.** Results depend only on the order of events (stream order =
  `observed_at` order), not on how they were split into batches. A test checks that one batch of
  N and N batches of 1 give identical output.
- **When detection fails (builder's call).** A rule that raises an exception on one event is a
  bug in that rule, not a reason to block the stream:
  - the error is caught **per rule, per event** and logged with the rule id and event id
  - it is counted (the evaluation report shows `rule_errors`, which should be 0)
  - the other rules still run, and the event is stored

  A database failure still rolls back the whole batch and retries it, as today. When the
  existing row-by-row storage fallback is used, each row's store and detection share one
  transaction. Detection state therefore stays consistent with what was stored, and the output
  still depends only on event order.

- **Single consumer.** Enrichment and correlation state is shared.
  `shortcut: one worker consumer only, partition the stream by principal/asset before running
worker ×N (M8 Helm)`. Compose already runs one worker.

### 6.2 Enrich

The worker keeps state in Postgres (schema `core`, new Alembic migration `0002`):

| Table        | Holds                                                                                                                                                                                                                                     |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `assets`     | `resource_uid`, `kind`, `first_seen`, `last_seen`, `deleted_at`, `ttl_seconds`, owner chain (pod → ReplicaSet → Deployment, pod → Job), `lifecycle_class`, `class_confidence`, `class_reason`. Rows are kept after deletion (tombstones). |
| `identities` | `principal_id`, `principal_type`, `federated_from`, `first_seen`, known networks (source /24s), known countries, and the last `(country, observed_at)` for impossible travel.                                                             |

Each event gets a **context** for rules to read:

- `asset.has_controller`, `asset.owner_kind`, `asset.age_s`
- `identity.new_network`, `identity.new_country`, `identity.impossible_travel`
- `time.off_hours` (builder's call: UTC business hours, set in config)

**Warm-up (builder's call).** "New network" means nothing on the first event of a fresh database.
So the evaluation first replays a **benign warm-up window**: routine and legitimate scenarios only,
timestamped just before the labelled window, from a separate seed. This lets identities and assets
build history, the way a real deployment learns its baseline. The warm-up must use the **same
world** as the labelled window: the same people with the same home countries and networks. Only
its scenario draws come from the separate seed. Otherwise every human would look like a new
country. Warm-up events are excluded from
every metric. The simulator gains a way to generate this benign-only window.

### 6.3 Classify (heuristics only)

Each asset is classified when it is first seen, and reclassified when it is deleted or its owner
becomes known. Each result has a class, a confidence and a one-line reason.

| Signal                                                                     | Class                   |
| -------------------------------------------------------------------------- | ----------------------- |
| Owner is a Job or CronJob, CI pipeline labels, spot market, autoscaler tag | ephemeral               |
| Deleted within N minutes of creation (config)                              | ephemeral               |
| Owned by a ReplicaSet, Deployment or StatefulSet and not deleted soon      | persistent              |
| Nothing conclusive                                                         | unknown, low confidence |

Ground truth for the metric comes from the label side (§6.7), never from these heuristics.

### 6.4 L1 rules

**Where they live.** YAML files in `libs/py/detection-core/rules/`. They are loaded and validated
at worker start, and an invalid rule stops the worker with a clear error.

**How they're validated.** Through a Pydantic model whose exported JSON Schema is committed next to
the rules (builder's call). This meets the spec's "JSON-Schema-validated" requirement without
adding a separate jsonschema dependency. YAML parsing adds PyYAML, pinned exactly.

**What a rule contains:**

- `id`, `version`, `title`, `severity`, `mitre[]`, `confidence`
- `match`: predicates over event fields and enrichment context: equals, in, prefix, contains,
  exists, not, all / any
- optional `unless`: documented exceptions such as an approved-exposure label

There are no free-form expressions or code in YAML. Every detection records the rule `id` and
`version`, the events it used, and a human-readable reason.

**Rule set:**

| Rule                            | Fires on                                                                                | MITRE         |
| ------------------------------- | --------------------------------------------------------------------------------------- | ------------- |
| `public-service-exposure`       | Service of type NodePort or LoadBalancer created                                        | T1190         |
| `sg-open-to-world`              | Security group ingress from `0.0.0.0/0`                                                 | T1190         |
| `privileged-pod-no-controller`  | Privileged or hostNetwork pod with no owner                                             | T1610 / T1611 |
| `miner-image-or-command`        | Known miner images or mining-like commands                                              | T1496         |
| `exec-into-pod`                 | `exec` into a pod in an application namespace                                           | T1609         |
| `cluster-admin-binding`         | RoleBinding or ClusterRoleBinding to `cluster-admin`                                    | T1098         |
| `session-from-new-network`      | Login or token use from a network or country new to that identity, or impossible travel | T1078         |
| `assume-admin-from-new-network` | AssumeRole into an admin role from a new network                                        | T1078         |

**Off-hours** is a context factor that raises confidence, not a rule of its own (builder's call).
The dataset's time window depends on `--start`, so an off-hours-only rule would measure the start
time rather than behaviour.

Look-alikes are **meant** to trigger some rules. For example, an on-call engineer's exec still
fires `exec-into-pod`. They're separated by score and correlation, not by hiding the rule. Rule
exceptions (`unless`) are added only during tuning on dev seeds, each with a written reason.

### 6.5 Correlate (simple v1) and incidents

**Grouping.** A new detection joins an open incident if both share an entity and fall within a
15-minute sliding window on `observed_at` (config). Shared entities are a `principal_id` plus
source IP, a `session_id`, a `resource_uid`, or the same owner-chain root. Otherwise the detection
starts a new incident. If one detection links two incidents, they merge, and the older id is kept.

**Shared service account.** `ci:deployer` is shared by CI and attackers. Grouping on the principal
alone would merge CI noise into attack incidents and lower purity, which is why principal grouping
uses the (principal, source IP) pair. Cluster purity will show whether this holds; any change is
tuned on dev seeds.

**Table: `incidents`.**

| Column                      | Holds               |
| --------------------------- | ------------------- |
| `incident_id`               | UUIDv7              |
| `status`                    | always `open` in M4 |
| `risk_score`                | 0–100               |
| `score_breakdown`           | JSONB               |
| `mitre[]`                   |                     |
| `first_seen` · `last_seen`  |                     |
| `entity_keys`               |                     |
| `created_at` · `updated_at` |                     |

**Table: `detections`.**

| Column                                | Holds                                                                                     |
| ------------------------------------- | ----------------------------------------------------------------------------------------- |
| `detection_id`                        |                                                                                           |
| `detector`                            | `rule:<id>@<version>`                                                                     |
| `event_ids[]`                         |                                                                                           |
| `resource_uid` · `principal_id`       |                                                                                           |
| `severity` · `confidence` · `mitre[]` |                                                                                           |
| `reason`                              |                                                                                           |
| `features`                            | JSONB                                                                                     |
| `observed_at` · `detected_at`         | `detected_at` comes from the worker's clock; it is used only for latency, never for logic |

The join table is **`incident_detections`**.

### 6.6 Score

The formula comes from the main spec §7:

```
resource_risk = severity × exposure_window_factor × privilege_factor × confidence
incident_risk = clamp(max(resource_risk) + breadth_bonus(#assets, #identities), 0, 100)
```

- `layer_agreement_bonus` is 0 in M4 (L1 only) and appears in the breakdown as `0 (L2/L3 not
built)`.
- All weights are in one config file. The breakdown stores every factor, so the API can show why
  a score is what it is.
- **Raised incidents (builder's call).** An incident is **raised** (an alert an analyst would see)
  when `risk_score ≥ alert_threshold`, initially 40. Incidents below it are kept and visible
  through the API but count as not raised. The threshold is part of the evaluation config,
  recorded in every report, and tuned only on dev seeds.

### 6.7 Simulator changes

**Two new attack scenarios, each with a legitimate look-alike** (decided):

| Scenario          | Malicious variant                                                                                                                                     | Look-alike                                                                                                                  |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `pod_exec`        | A stolen service-account token, or a human from a new network, opens an interactive exec into a running application pod and runs recon-like commands. | An on-call engineer, from their usual network after a normal login with MFA, execs into the same kind of pod.               |
| `rbac_escalation` | A ClusterRoleBinding to `cluster-admin` created by an identity that doesn't normally change RBAC, often after a session from a new network.           | The platform team's approved change: a binding created by the usual automation or platform identity from the usual network. |

- Both must keep the no-giveaway test green: the attackers' user agents and /24s also appear in
  benign traffic.
- The approval signal for the look-alikes must be a field a real cluster would carry, such as an
  annotation or a ticket label. It must not be a field only the simulator knows.

**Placement in the challenge mix (builder's call).** These two are new **variants**, not new
scenario names. That follows the existing pattern, where a look-alike lives inside its scenario,
like the approved-sandbox twin in `exposure.py`, and it keeps the challenge proportions in `MIX`
unchanged:

- the malicious exec and RBAC variants join `identity_anomaly`: stolen or misused identities
  doing something new
- the on-call exec and the approved platform binding join `routine_lifecycle`

**Labels gain `variant`.** A label-side field such as `pod_exec`, `rbac_escalation` or
`oncall_exec` lets the report show results per variant, so every rule's coverage is visible.

**Labels gain `asset_class`.** The values are `ephemeral`, `persistent`, or null for events with no
asset, such as logins. It is set per event from the scenario's design intent: what the asset is
meant to be. It lives only in `core.event_labels`, in a new nullable column added in migration
`0002`, and in the JSONL label. It is never on the stream.

**Also:**

- a benign-only warm-up mode (§6.2)
- the golden digest updated as noted in §5

### 6.8 Leakage guard

An import-linter contract forbids `ephoros_detection` and `ephoros_api` from importing
`ephoros_sim` or the evaluation package (builder's call). No code path in the worker or API reads
`core.event_labels`. A test asserts that the worker's database role, or at least its query
surface, never selects from it (builder's call: a simple grep-style test over the adapters is
acceptable).

### 6.9 Evaluation harness (`just evaluate`)

**Package.** A new uv workspace member `libs/py/evaluation` (`ephoros_eval`, CLI `ephoros-eval`).
It depends on the simulator, asyncpg and testcontainers, all pinned exactly (builder's call).

**Run (builder's call):**

1. Start throwaway Postgres and Redis with Testcontainers, so no dev data is ever touched, and run
   the Alembic migrations.
2. Launch the **real worker** as a subprocess (`ephoros-worker`) pointed at those stores. The
   worker's shared `Settings` requires `JWKS_URL` and `JWT_ISSUER`, which the worker never uses;
   the harness passes placeholder values for them.
3. Replay the warm-up window, then the labelled window, with the simulator's existing publish
   code. Labels are written first, as today. Warm-up and labelled windows get different `run_id`s
   in `core.event_labels`. Metrics use only the labelled run's events and any incident containing
   them.
4. Wait until the stream is drained and nothing is pending, with a timeout that fails loudly.
5. Read detections and incidents from the database, join labels by `event_id`, and compute the
   metrics.
6. Write the report and stop everything.

**Seeds (builder's call).** Dev seeds `1, 2, 3` are used for tuning. The held-out seed is
`20261029`, which no test uses. `just evaluate` defaults to the held-out seed; `just evaluate
--seed 1` runs a dev seed. CI runs the held-out seed. Tuning decisions are made from dev-seed
reports only; the held-out result is reported, not tuned against.

**Unit of measurement and matching (decided: strict definitions).**

- Each raised incident is **matched** to the scenario instance (for example `crypto_mining-004`)
  that contributes the most of the incident's labelled events. Ties go to the instance with the
  earliest event.
- **One attack, one catch.** A malicious instance is **caught** when at least one raised incident
  is matched to it. Only the earliest such incident is a true positive. Every other raised
  incident matched to the same instance is a **duplicate**, and counts as a false positive.
- **False positives** are raised incidents matched to a benign instance (look-alikes, routine,
  legit bursts) plus duplicates.
- Precision = TP ÷ raised incidents. Recall = caught malicious instances ÷ malicious instances.

**Metrics:**

| Metric (§1.3)                                                           | M4 status                           | How                                                                                                                                                                                                                                                                                             |
| ----------------------------------------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ephemeral asset visibility (recall of the ephemeral class)              | measured                            | assets table class vs. `asset_class` truth (per asset, majority of its labelled events)                                                                                                                                                                                                         |
| Detection latency p95 (alert pushed to UI)                              | **not yet measured** (needs M5 SSE) | Report shows worker processing time (`detected_at − ingested_at`) as information only, not against the target.                                                                                                                                                                                  |
| Noise reduction = 1 − incidents ÷ raw detections                        | measured                            | Judged against the target on **raised** incidents (the queue an analyst sees). The all-incident figure is also reported, as information (decided).                                                                                                                                              |
| Legit-burst suppression = share of legit bursts with no raised incident | measured                            | Covers only `legit_burst` instances. A burst is **unsuppressed** if any raised incident contains even one of its events (decided). Benign look-alikes still count through false positives. The metric is defined by outcome, so it is measurable now. The L2 suppression mechanism is still M6. |
| Incident correlation (mean cluster purity)                              | measured                            | share of each raised incident's events from its matched instance                                                                                                                                                                                                                                |
| Risk scoring vs. analyst judgment (Spearman ρ)                          | measured                            | incident `risk_score` vs. matched instance's labelled severity, across all incidents                                                                                                                                                                                                            |
| Malicious precision / recall                                            | measured                            | precision over raised incidents; recall over malicious instances                                                                                                                                                                                                                                |
| Narrative citation validity                                             | **not yet measured** (M7)           |                                                                                                                                                                                                                                                                                                 |
| MITRE match on 3 reference incidents                                    | measured (builder's call)           | One reference instance each of mining (T1496), exposure (T1190) and identity misuse (T1078); the expected techniques live in the evaluation config, not in the simulator labels.                                                                                                                |

**Report content.** The report also has:

- a per-scenario table: instances, caught, missed, and why if known
- every missed instance listed by id
- false positives listed with their incident ids
- the ablation table with L1 measured and L1+L2 / L1+L2+L3 as not yet measured

**Report header:**

- seed and warm-up seed
- simulator version and dataset digest
- git commit
- rule set id@version list
- scoring weights and alert threshold
- run time

The same seed on the same commit must produce identical metrics, and a test runs the evaluation
twice to check this.

**Outputs:**

| File                         | What it is                                                                                                                                                                                                                                                                          |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/evaluation/report.md`  | Latest headline report, committed                                                                                                                                                                                                                                                   |
| `docs/evaluation/runs.jsonl` | One line per run, appended: seed, commit, metrics, statuses, short note. This is the tuning log the owner asked for (decided: every run recorded). It replaces the spec's `eval_runs` table for M4, because the evaluation database is thrown away after each run (builder's call). |

**Edge cases.** A metric with no data counts as a **fail** in the report, never as a pass. Examples:
precision with zero raised incidents, or Spearman with fewer than three incidents.

**Exit codes and CI (decided).**

`ephoros-eval` separates two kinds of failure.

| Exit code | Meaning                                                                          |
| --------- | -------------------------------------------------------------------------------- |
| **0**     | The evaluation ran and every measured metric passes                              |
| **1**     | The evaluation ran but a measured metric misses its target (the report names it) |
| **2**     | **The evaluation could not run properly**, so its numbers can't be trusted       |

Exit 2 covers:

- containers fail to start
- migrations fail
- the worker dies
- the stream doesn't drain before the timeout
- events are dead-lettered unexpectedly
- `rule_errors > 0`
- the warm-up or labelled run is missing

_Not yet measured_ never causes a non-zero exit.

**CI modes:**

| Mode            | When                              | Exit 2 (infrastructure error) | Exit 1 (missed target)                             |
| --------------- | --------------------------------- | ----------------------------- | -------------------------------------------------- |
| **Report-only** | During M4                         | Fails the job                 | Doesn't fail the job: `--report-only` maps it to 0 |
| **Blocking**    | Once every measured target passes | Fails the job                 | Fails the job, so it guards against regressions    |

Switching to blocking is a one-line change: drop `--report-only`.

In both modes, the job runs `just evaluate` on the held-out seed, uploads the report as an
artifact, and writes the pass / fail / not-yet-measured table to the job summary. The owner edits
CI workflows and pushes them, so the CI change is proposed as a diff for the owner to apply.

**M4 is done when (decided):**

- every measured target passes, **or**
- each remaining miss has been investigated, tuned on dev seeds, reported honestly, and
  documented in an ADR the owner approves.

A target is never weakened without an approved ADR.

**When a target is missed** (decided):

1. Investigate the false positives or misses.
2. Make only defensible rule or weight changes, tuned on dev seeds.
3. Re-run and log each change.
4. Check recall alongside precision.
5. If the target is still missed, report it honestly. Never weaken a target or edit the dataset.
   Recalibrating a target, which the main spec §1.3 allows, needs an ADR with the reason and the
   owner's approval.

**Tests for the definitions.** The strict matching rules get pure-function tests on hand-built
cases:

- a duplicate alert counts as a false positive
- a tie goes to the instance with the earliest event
- one event inside a raised incident marks its burst unsuppressed
- zero raised incidents is a fail

### 6.10 Incident API

| Endpoint                                      | Returns                                                                                                                                                                                                                                                                                     |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/v1/incidents?limit&cursor&min_risk` | Page of incidents: id, risk_score, raised (bool), status, mitre, first/last_seen, counts of detections, assets and identities. Keyset pagination on `(last_seen, incident_id)`, newest first, cursor in the same style as `/events`.                                                        |
| `GET /api/v1/incidents/{id}`                  | The incident plus `score_breakdown`; its detections (rule id@version, title, severity, confidence, mitre, reason); and evidence events (up to 50, oldest first, **including `raw`**, in line with the main spec's "evidence stays server-side until incident detail"). 404 as problem+json. |

- **Auth:** a router-level `Depends(current_user)`. The existing guard test automatically covers
  the new routes.
- **Conventions:** return types, documented 401 and 404 responses (and 400 for a bad cursor), and
  the generated client regenerated so `just check-contract` stays clean.
- **Not in M4:** triage writes (`PATCH`).

## 7. Testing

- **detection-core unit tests:**
  - each rule, for both its attack and its look-alike
  - the rule schema rejecting bad YAML
  - classifier heuristics
  - scoring breakdown arithmetic
  - correlation grouping and merging
  - the batch-independence test
- **API tests:** the incident endpoints (auth, pagination, 404, evidence includes `raw`).
- **Integration test (Testcontainers):** worker store and detect in one transaction, and
  redelivery creating no duplicate detections.
- **Simulator tests:** the new scenarios exist with their look-alikes, the no-giveaway test stays
  green across seeds, `asset_class` is present, and the golden digest is updated.
- **Evaluation tests:** the metric functions on small hand-built fixtures (pure functions), and
  the determinism check (§6.9).
- **Verification before done:** lint, typecheck, test and build for all projects, plus `just e2e`.

## 8. Left to the builder (the implementation plan)

- task order and commit boundaries
- exact predicate syntax in rule YAML
- exact config file names and layout
- index choices on the new tables
- the precise ephemeral TTL cutoff and scoring weights, as starting values, tuned on dev seeds
- how the warm-up window is generated (a flag or a separate function), as long as it is benign-only
  and seeded
- report formatting
