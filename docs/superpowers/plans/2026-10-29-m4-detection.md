# Milestone 4: Detection v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The worker turns every stored event into incidents. It enriches the event, classifies
assets with heuristics, runs the L1 YAML rules, correlates detections and scores them, all in the
same transaction that stores the event. `GET /api/v1/incidents[/{id}]` shows the score breakdown,
the rules that fired and the evidence. `just evaluate` replays a held-out labelled dataset through
the real worker and writes a measured, honest report.

**Architecture:** The detection logic is pure, async and framework-free, in `ephoros_detection`. It
reads state through a `StateView` protocol and returns a `Changes` value. The API package adds a
SQL `DetectionStore` adapter: one transaction per batch, holding the event insert, the state reads
and the detection writes. `IngestService` calls it. A new workspace package, `libs/py/evaluation`
(`ephoros_eval`), starts Testcontainers stores and runs the real `ephoros-worker` as a subprocess.
It replays a warm-up window and then the labelled window, reads the database, and scores the run
with pure metric functions.

**Tech Stack:** Python 3.13 · pydantic 2 · PyYAML `6.0.3` (new, detection-core) · SQLAlchemy 2.1.5
async · Alembic 1.20.0 · testcontainers 4.15.0 · asyncpg 0.32.0 · FastAPI 0.150.0 ·
`statistics.correlation(method="ranked")` for Spearman (stdlib, no scipy).

**Spec:** `docs/superpowers/specs/2026-10-29-m4-detection-design.md` (the M4 design wins over
`2026-10-10-ephoros-design.md` where they differ).

## Global Constraints

- The M1–M3 plans' Global Constraints still hold. Run every command under
  `eval "$(mise env -s bash)"`.
- **Pins:**
  - exact versions only
  - new runtime dependency: `pyyaml==6.0.3` in `ephoros-detection`
  - `ephoros-eval` depends on `ephoros-simulator`, `ephoros-api` and `ephoros-detection` (all
    workspace), plus `asyncpg==0.32.0` and `testcontainers[postgres,redis]==4.15.0`
  - nothing else is added
- **Labels never reach detection:**
  - `ephoros_detection` and `ephoros_api` never import `ephoros_sim` or `ephoros_eval`
  - nothing outside `ephoros_eval`, `ephoros_sim` and the migrations names `event_labels`
- **Time comes from events:** every time-based decision uses `Event.observed_at`.
  `datetime.now` is used only for `detected_at` and `ingested_at`.
- **Deterministic ids:**
  - `detection_id = uuid5(DETECTION_NS, f"{detector}|{trigger_event_id}")`
  - `incident_id` = the `detection_id` of the incident's first detection
  - the same seed therefore gives the same ids
- **Severity:** `Severity = Literal["none", "low", "medium", "high", "critical"]` (the simulator's
  type). The ordinal used for Spearman is none 0, low 1, medium 2, high 3, critical 4.
- **Starting scoring values** (`ephoros_detection/config.py`, `DetectionConfig` defaults; tune
  later on dev seeds only):

  | Setting                  | Value                                                                                                         |
  | ------------------------ | ------------------------------------------------------------------------------------------------------------- |
  | severity points          | low 10 · medium 25 · high 45 · critical 65                                                                    |
  | `privilege_factor`       | 1.5 if the detection's features have `privileged` / `host_network` / `admin_role` / `cluster_admin`, else 1.0 |
  | `exposure_window_factor` | 1.2 if features have `public`, else 1.0                                                                       |
  | context boost            | confidence × 1.25 (capped at 1.0) when `identity_new_network` or `off_hours`                                  |
  | `breadth_bonus`          | 5 × ((#assets − 1) + (#identities − 1)), capped at 20                                                         |
  | `layer_agreement_bonus`  | 0                                                                                                             |
  | `alert_threshold`        | 40                                                                                                            |
  | `correlation_window`     | 15 min                                                                                                        |
  | `ephemeral_ttl`          | 30 min                                                                                                        |
  | business hours           | 07:00–19:00 UTC, Mon–Fri                                                                                      |

- **Seeds:**
  - dev seeds are `1, 2, 3`; the held-out seed is `20261029`, and no test may use it
  - the warm-up window is 2 h ending at the labelled start, drawn from seed `labelled_seed + 1000`
    but with the **labelled seed's world**
  - the labelled start is fixed at `2026-01-05T08:00:00Z`
- **Targets** (`ephoros_eval/targets.py`; changing one needs an ADR approved by the owner):

  | Metric                  | Target       |
  | ----------------------- | ------------ |
  | ephemeral recall        | ≥ 0.95       |
  | noise reduction         | ≥ 0.40       |
  | legit-burst suppression | ≥ 0.90       |
  | purity                  | ≥ 0.85       |
  | Spearman                | ≥ 0.70       |
  | precision               | ≥ 0.85       |
  | recall                  | ≥ 0.85       |
  | MITRE                   | 3/3          |
  | latency p95             | not measured |
  | narrative validity      | not measured |

- **Exit codes of `ephoros-eval`:**

  | Code | Meaning                                              |
  | ---- | ---------------------------------------------------- |
  | 0    | Every measured metric passes                         |
  | 1    | A measured metric fails, or has no data              |
  | 2    | The run broke: exception, drain timeout, worker died |

- **Process (unchanged):**
  - Per task: TDD → ponytail (smallest code) → verification → ponytail-review → fix → commit
    (`&& echo committed`).
  - Milestone end: lint, typecheck, test and build for all projects, plus `just e2e`; then a fresh
    whole-branch review → ponytail-debt → finishing-a-development-branch.
  - Commit locally only. **Never push.** The `.github/workflows` change is handed to the owner as
    a diff (Task 11).

## Review Focus

1. **Redelivery after a crash mid-batch:** no duplicate detections and no lost detections. Test
   in Task 7: `test_redelivered_batch_creates_no_duplicate_detections`.
2. **A rule raising on an odd event:** the event is stored, the other rules still run, and
   `rule_errors` is counted. Test in Task 6: `test_rule_exception_is_isolated`.
3. **Batch boundaries change the result:** one batch of N vs N batches of 1 must give identical
   `Changes`. Test in Task 6: `test_batch_split_does_not_change_output`.
4. **Label leakage through a new import or query:** Task 9 adds the import-linter contract
   `labels-never-reach-detection`, plus `test_only_eval_and_sim_mention_event_labels`.
5. **A metric with no data reads as a pass:** zero raised incidents, or fewer than 3 incidents
   for Spearman, must be `fail`. Test in Task 9: `test_empty_inputs_fail_not_pass`.

---

### Task 1: Simulator labels gain `variant` and `asset_class`; benign warm-up window

**Files:**

- Modify:
  - `libs/py/simulator/src/ephoros_sim/{model,generate,labels,replay}.py`
  - `libs/py/simulator/src/ephoros_sim/scenarios/{__init__,*.py}`
  - `apps/api/src/ephoros_api/adapters/db/tables.py`
- Create: `apps/api/migrations/versions/0002_label_variant_and_asset_class.py`
- Test: `libs/py/simulator/tests/test_generate.py`, `test_replay.py`

**Interfaces:**

- **Produces `Label`:**
  - existing fields: `scenario`, `is_malicious`, `severity`, `scenario_instance_id`
  - new: `variant: str`
  - new: `asset_class: Literal["ephemeral", "persistent"] | None`, per record. `Label` stays
    per-record (frozen), so scenarios attach `asset_class` per record.
- **Produces `Instance.records`:** items become
  `(ts, source, raw, variant, asset_class)`, set only on lifecycle events (create/delete,
  RunInstances/TerminateInstances) of Pod, Job, CronJob, Service, Instance, Deployment, ReplicaSet
  and StatefulSet, and `None` elsewhere. Every scenario sets its variant name.
- **Produces `generate`:**
  `generate(seed, start, hours=6.0, *, benign_only=False, world_seed=None) -> list[SimRecord]`.
  - `world_seed` defaults to `seed`, and the world is built from `random.Random(world_seed)`
    before any scenario draws
  - `benign_only=True` plans only `legit_burst` and `routine_lifecycle` in their MIX ratio and
    skips `_check_volumes`
- **Produces `core.event_labels`:** new columns `variant text not null default ''` and
  `asset_class text null`, written by `write_labels`.

- [ ] **Step 1: Write the failing tests**
  - `test_every_record_has_a_variant`: for seeds 1, 2 and 7, every `label.variant` is non-empty.
  - `test_asset_class_only_on_lifecycle_events`: for each normalized event,
    `label.asset_class is not None` ⇔ (`action` ∈ {create, delete, run_instances,
    terminate_instances} and `kind` is in the asset kinds above).
  - `test_job_owned_pods_are_ephemeral_and_rs_pods_persistent` (seed 7):
    - pods with `owner_ref.kind == "Job"` have `asset_class == "ephemeral"`
    - pods created by the routine rollout with `owner_ref.kind == "ReplicaSet"` have
      `"persistent"`
  - `test_warmup_is_benign_and_shares_the_world`:
    - every record of `generate(1001, start - 2h, 2.0, benign_only=True, world_seed=1)` has
      `is_malicious` False
    - the set of `(principal, ip)` pairs of humans in it is a subset of seed 1's world people
  - `test_labels_round_trip_new_fields` (test_replay): `write_jsonl` → `read_jsonl` keeps
    `variant` and `asset_class`.

- [ ] **Step 2: Run the tests and confirm they fail**
      Run `uv run pytest libs/py/simulator -q`. Expected: FAIL on the new tests (attribute errors).

- [ ] **Step 3: Implement**
  - Set the variant names: `crypto_mining`: `miner` / `miner_gpu`; `exposure`: `sg_world` /
    `debug_service` / `approved_sandbox`; `identity_anomaly`: `stolen_human` / `automation_new_net`
    / `federated_admin`; `legit_burst`: `ci_fanout` / `autoscaler`; `routine_lifecycle`: `routine`.
  - Assign `asset_class` by design intent:

    | Asset                                                                                            | Class      |
    | ------------------------------------------------------------------------------------------------ | ---------- |
    | CI Job and its pods, miner pod, debug pod and service, spot instances (miner GPU and autoscaler) | ephemeral  |
    | Rollout ReplicaSet and its pods                                                                  | persistent |
    | Replaced old pods in routine                                                                     | persistent |

  - Migration `0002`: `op.add_column` for both columns, plus a downgrade.

- [ ] **Step 4: Update the golden digest and verify**
  - Recompute `GOLDEN_SEED_7` and say why in the commit body.
  - Run `uv run pytest libs/py/simulator apps/api/tests -q` and
    `uv run alembic -c apps/api/alembic.ini check` against a migrated database (the integration
    fixture). Expected: all pass, and `test_no_single_field_gives_the_label_away` stays green.

- [ ] **Step 5: Commit**
      `feat(sim): label variants and asset classes, and generate a benign warm-up window`

### Task 2: Simulator: exec and RBAC attacks with look-alikes

**Files:**

- Modify:
  - `libs/py/simulator/src/ephoros_sim/scenarios/{identity_anomaly,routine}.py`
  - `libs/py/simulator/src/ephoros_sim/records.py` (`k8s(namespace: str | None)` for
    cluster-scoped objects)
  - `libs/py/simulator/src/ephoros_sim/world.py` (`PLATFORM_SA`, and
    `CHANGE_LABEL = "change.corp.example/ticket"`)
- Test: `libs/py/simulator/tests/test_generate.py`

**Interfaces:**

- **Consumes:** Task 1's per-record variant and `asset_class`.
- **Produces, inside `identity_anomaly`:** `variant = k % 5`, with 0–2 unchanged.
  - **3 `pod_exec`:** a token from `attacker_ip`, or a person from a VPN range, then a k8s exec
    (`subresource="exec"`, `code=101`) into an app pod in `APP_NAMESPACES`. Severity `high`.
  - **4 `rbac_escalation`:** a login or token from a new network, then a `create
clusterrolebindings` whose body is `{"roleRef": {"name": "cluster-admin"}, "subjects": [...]}`,
    with no change label. Severity `critical`.
- **Produces, inside `routine_lifecycle`:** for `k % 4 == 1`, add an `oncall_exec` (a person from
  their home IP, after login and MFA, execs into an app pod). For `k % 4 == 3`, add an
  `approved_binding` (`PLATFORM_SA` from `ci_ip` creates a cluster-admin binding whose metadata
  labels carry `CHANGE_LABEL: CHG-<n>`). These stay `is_malicious=False`, severity `none`.

- [ ] **Step 1: Write the failing tests**
  - `test_exec_and_rbac_attacks_and_lookalikes_exist`: for seeds 1, 2 and 7, each of the variants
    `pod_exec`, `rbac_escalation`, `oncall_exec` and `approved_binding` appears at least once.
  - `test_exec_and_binding_normalize`:
    - every exec record normalizes to `action == "exec"`
    - every binding record normalizes to `category == "rbac"`, `action == "bind_role"` and
      `attributes["role_ref"] == "cluster-admin"`
  - Keep `test_scenario_mix_is_in_range` and `test_no_single_field_gives_the_label_away` unchanged
    and green.

- [ ] **Step 2: Run the tests and confirm they fail.** Then implement, re-run (all green), update
      the golden digest again with the reason, and commit:
      `feat(sim): add pod-exec and cluster-admin binding attacks with legitimate look-alikes`

### Task 3: Rules: schema, YAML loader, predicate evaluation, the eight M4 rules

**Files:**

- Create:
  - `libs/py/detection-core/src/ephoros_detection/rules/{__init__,model,engine}.py`
  - `libs/py/detection-core/src/ephoros_detection/rules/builtin/*.yaml` (8 files)
  - `libs/py/detection-core/src/ephoros_detection/rules/rule.schema.json`
- Modify: `libs/py/detection-core/pyproject.toml` (`pyyaml==6.0.3`), `uv.lock`
- Test: `libs/py/detection-core/tests/test_rules.py`

**Note:** the rules live inside the package, not in `libs/py/detection-core/rules/`, so they ship in
the worker image. This deviates from the design's path, on purpose.

**Interfaces:**

- **Produces the rule model:**
  ```python
  Op = Literal["eq", "in", "prefix", "contains", "exists", "gte"]
  class Predicate(BaseModel): field: str; op: Op; value: Any = None        # extra="forbid"
  class Match(BaseModel): all: list["Predicate | Match"] = []; any: list[...] = []; none: list[...] = []
  class Rule(BaseModel):
      id: str  # ^[a-z0-9-]+$
      version: int  # >= 1
      title: str; severity: Severity; confidence: float  # 0 < c <= 1
      mitre: list[str]  # each ^T\d{4}(\.\d{3})?$, min 1
      match: Match; unless: list[Match] = []
      features: list[str] = []  # tags copied into Detection.features, e.g. "public", "privileged"
  class RuleError(Exception): ...  # message names the file
  def load_rules(directory: Path | None = None) -> list[Rule]  # default: the builtin dir; sorted by id
  def matches(rule: Rule, fields: Mapping[str, Any]) -> bool  # match and no unless matches
  ```
- **Produces the field names rules may use** (built in Task 4 by `fields(event, ctx)`):
  - `action`, `category`, `outcome`, `source`
  - `actor.principal_id`, `actor.principal_type`, `actor.source_ip`
  - `resource.kind`, `resource.namespace`, `resource.labels.<key>`, `resource.owner_kind`
  - `attributes.<key>`
  - `ctx.has_controller`, `ctx.new_network`, `ctx.new_country`, `ctx.impossible_travel`,
    `ctx.off_hours`
- **Produces the rule set:**

  | `id`                            | Severity / confidence / MITRE / features | Condition                                                                                                                           |
  | ------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
  | `public-service-exposure`       | high / 0.9 / T1190 / public              | `resource.kind` eq Service and `attributes.service_type` in [NodePort, LoadBalancer]; unless `resource.labels.exposure` eq approved |
  | `sg-open-to-world`              | high / 0.9 / T1190 / public              | action eq modify_sg and `attributes.sg_rules` contains cidr `0.0.0.0/0`                                                             |
  | `privileged-pod-no-controller`  | high / 0.8 / T1610, T1611 / privileged   | kind Pod, action create, `ctx.has_controller` eq false, and any of `attributes.privileged` or `attributes.host_network` eq true     |
  | `miner-image-or-command`        | critical / 0.9 / T1496                   | kind Pod, action create; any of image contains xmrig, command contains `pool.`, command contains `sha256sum /dev/zero`              |
  | `exec-into-pod`                 | medium / 0.7 / T1609                     | action exec, kind Pod, `resource.namespace` in APP_NAMESPACES                                                                       |
  | `exec-from-new-network`         | high / 0.85 / T1609, T1078               | same as `exec-into-pod`, plus `ctx.new_network` eq true                                                                             |
  | `cluster-admin-binding`         | high / 0.8 / T1098 / cluster_admin       | action bind_role and `attributes.role_ref` eq cluster-admin; unless `resource.labels.change.corp.example/ticket` exists             |
  | `session-from-new-network`      | medium / 0.6 / T1078                     | action in [login, token_issued, assume_role]; any of `ctx.new_network`, `ctx.new_country`, `ctx.impossible_travel`                  |
  | `assume-admin-from-new-network` | high / 0.8 / T1078 / admin_role          | action assume_role, `resource.kind` Role, resource uid contains `:role/admin`, `ctx.new_network` true                               |

  That is nine files. The extra rule is `exec-from-new-network`; the design's eight families are
  all covered. The `contains` op on a list of dicts matches when any element's values contain the
  value.

- [ ] **Step 1: Write the failing tests**
  - `test_builtin_rules_load_and_ids_are_unique`: there are 9 rules, and their ids are unique and
    sorted.
  - `test_schema_file_matches_model`:
    `json.loads(schema_file) == Rule.model_json_schema()`. Regenerate with
    `uv run python -m ephoros_detection.rules`.
  - `test_invalid_rule_names_the_file`: a tmp dir with a rule missing `mitre` →
    `RuleError` whose message contains the file name.
  - `test_unknown_op_rejected`, `test_mitre_id_format_enforced`.
  - `test_matches_all_any_none_and_unless`: table-driven, over small dicts.
  - `test_each_rule_fires_on_its_attack_and_not_on_its_lookalike`: hand-built `fields` dicts, one
    attack and one look-alike per rule. Examples: an approved-label Service → no match; a Job-owned
    privileged pod (`ctx.has_controller` true) → no match.

- [ ] **Step 2: Run the tests and confirm they fail.** Implement, then run
      `uv run pytest libs/py/detection-core -q && uv run mypy`. Expected: PASS.

- [ ] **Step 3: Commit**
      `feat(detection): L1 rules as validated YAML with a small predicate engine`

### Task 4: Enrich and classify (pure)

**Files:**

- Create: `libs/py/detection-core/src/ephoros_detection/{config,state,enrich,classify}.py`
- Test: `libs/py/detection-core/tests/test_enrich.py`, `test_classify.py`

**Interfaces:**

```python
# config.py
class DetectionConfig(BaseModel): ...  # every value from Global Constraints, as defaults

# state.py (frozen pydantic models)
LifecycleClass = Literal["ephemeral", "persistent", "unknown"]
class AssetState(BaseModel): resource_uid; kind; first_seen; last_seen; deleted_at: datetime | None
    owner_kind: str | None; owner_uid: str | None; root_uid: str; labels: dict[str, str]
    spot: bool; lifecycle_class: LifecycleClass; class_confidence: float; class_reason: str
class IdentityState(BaseModel): principal_id; principal_type; federated_from: str | None
    first_seen; networks: frozenset[str]; countries: frozenset[str]
    last_country: str | None; last_country_at: datetime | None
class Context(BaseModel): has_controller: bool | None; owner_kind: str | None
    asset_age_s: float | None; new_network: bool; new_country: bool
    impossible_travel: bool; off_hours: bool

# enrich.py
ASSET_KINDS: frozenset[str]  # Pod, Job, CronJob, Service, Instance, Deployment, ReplicaSet, StatefulSet
def network(ip: str | None) -> str | None          # IPv4 /24 as "a.b.c", None for None
def enrich(event, asset: AssetState | None, owner: AssetState | None, identity: IdentityState | None,
           cfg: DetectionConfig) -> tuple[Context, AssetState | None, IdentityState]
def fields(event: Event, ctx: Context) -> dict[str, Any]  # the flat names from Task 3

# classify.py
def classify(asset: AssetState, cfg: DetectionConfig) -> tuple[LifecycleClass, float, str]
```

**Rules for the implementer:**

- An asset is created or updated only for lifecycle events of `ASSET_KINDS`. `root_uid` is the
  owner's `root_uid` when the owner is known, otherwise the asset's own uid.
- The `new_*` flags are computed **before** adding the event's network or country to the identity.
- `impossible_travel`: the country differs from `last_country` within 1 h.
- `off_hours`: from `observed_at` and the configured business hours.

**Classification heuristics, in order (first hit wins):**

| Heuristic                                        | Class / confidence |
| ------------------------------------------------ | ------------------ |
| Owner kind Job or CronJob                        | ephemeral / 0.95   |
| `spot` or label `autoscaler=true`                | ephemeral / 0.9    |
| Any label key starting `ci.`                     | ephemeral / 0.9    |
| Deleted with `ttl ≤ ephemeral_ttl`               | ephemeral / 0.85   |
| Owner kind ReplicaSet, Deployment or StatefulSet | persistent / 0.8   |
| Otherwise                                        | unknown / 0.3      |

Each result carries a one-line reason, for example `"owned by Job build-p1234"`.

- [ ] **Step 1: Write the failing tests**
  - `test_first_event_of_identity_is_new_network_then_not`
  - `test_new_flags_ignore_missing_ip`
  - `test_impossible_travel_within_an_hour_only`
  - `test_off_hours_uses_observed_at_not_now`
  - `test_owner_chain_root`: pod → ReplicaSet → Deployment gives the Deployment's uid
  - `test_delete_sets_deleted_at_and_ttl`
  - one test per heuristic row, plus `test_unknown_when_nothing_conclusive`
  - `test_fields_names_match_rules`: every `field` used in the builtin rules is either a key of
    `fields(...)` or a dynamic `labels.`/`attributes.` path

- [ ] **Step 2: Run the tests and confirm they fail.** Implement, re-run, and commit:
      `feat(detection): enrich events with asset and identity context and classify lifecycles`

### Task 5: Correlate and score (pure)

**Files:**

- Create: `libs/py/detection-core/src/ephoros_detection/{detections,correlate,score}.py`
- Test: `libs/py/detection-core/tests/test_correlate.py`, `test_score.py`

**Interfaces:**

```python
# detections.py
DETECTION_NS: UUID  # fixed constant
class Detection(BaseModel): detection_id: UUID; detector: str  # "rule:<id>@<version>"
    event_ids: list[UUID]; observed_at: datetime; principal_id: str; source_ip: str | None
    session_id: str | None; resource_uid: str; root_uid: str | None
    severity: Severity; confidence: float; mitre: list[str]; reason: str; features: dict[str, Any]
class IncidentState(BaseModel): incident_id: UUID; first_seen; last_seen
    entity_keys: frozenset[str]; detections: list[Detection]; risk_score: float
    raised: bool; score_breakdown: dict[str, Any]; mitre: list[str]
def entity_keys(d: Detection) -> frozenset[str]
    # "p:<principal>|<ip>", "s:<session>", "r:<resource_uid>", "o:<root_uid>"; None parts skipped

# correlate.py
def attach(d: Detection, candidates: Sequence[IncidentState], cfg) -> tuple[IncidentState, list[UUID]]
    # candidates sharing a key with last_seen >= d.observed_at - window; none → a new incident with
    # incident_id = d.detection_id; several → merge into the one with the smallest first_seen,
    # then id; returns (incident, ids merged away)

# score.py
def score(detections: Sequence[Detection], cfg) -> tuple[float, dict[str, Any]]
```

**Score breakdown:** the keys are `resources` (per resource uid: `severity_points`,
`exposure_window_factor`, `privilege_factor`, `confidence`, `resource_risk`), `max_resource_risk`,
`breadth_bonus`, `layer_agreement_bonus` (`{"value": 0, "note": "L2/L3 not built"}`) and `total`.
`total` is the formula from the spec, clamped to 0–100 and rounded to 1 decimal.

- [ ] **Step 1: Write the failing tests**
  - **Correlation:**
    - `test_shared_principal_ip_inside_window_joins`
    - `test_same_principal_other_ip_does_not_join` (the shared `ci:deployer`)
    - `test_outside_window_starts_new`
    - `test_bridge_detection_merges_and_keeps_oldest`
  - **Scoring:**
    - `test_score_breakdown_arithmetic` (one high privileged detection at confidence 0.8 →
      45 × 1 × 1.5 × 0.8 = 54.0)
    - `test_breadth_bonus_capped_at_20`
    - `test_clamped_to_100`
    - `test_layer_agreement_is_zero_and_explained`

- [ ] **Step 2: Run the tests and confirm they fail.** Implement, re-run, and commit:
      `feat(detection): correlate detections into incidents and score them with a breakdown`

### Task 6: `DetectionPipeline` (pure orchestration over a `StateView`)

**Files:**

- Create: `libs/py/detection-core/src/ephoros_detection/pipeline.py`
- Test: `libs/py/detection-core/tests/test_pipeline.py` (with an in-memory `StateView` in the test
  module)

**Interfaces:**

```python
class StateView(Protocol):
    async def asset(self, uid: str) -> AssetState | None: ...
    async def identity(self, principal_id: str) -> IdentityState | None: ...
    async def incidents_touching(self, keys: frozenset[str], since: datetime) -> list[IncidentState]: ...

@dataclass
class Changes:
    assets: dict[str, AssetState]; identities: dict[str, IdentityState]
    detections: list[Detection]; incidents: dict[UUID, IncidentState]
    merged_away: set[UUID]; rule_errors: int

class DetectionPipeline:
    def __init__(self, rules: Sequence[Rule], cfg: DetectionConfig) -> None
    async def process(self, events: Sequence[Event], state: StateView) -> Changes
```

**Rules for the implementer:**

- Events are processed in `(observed_at, event_id)` order.
- Reads go first to this call's own pending `Changes`, then to `state`, so the result does not
  depend on how events are batched.
- A rule raising any `Exception` on an event: log a warning with the rule id and event id,
  increment `rule_errors`, and continue.
- After each attach, re-score the incident and set `raised = risk_score >= cfg.alert_threshold`.

- [ ] **Step 1: Write the failing tests**
  - `test_miner_pod_events_become_one_raised_incident`: hand-built events (token from a new
    network, a privileged unowned xmrig pod) → one incident, `raised` True, mitre contains T1496.
  - `test_ci_dind_pod_raises_nothing`: Job-owned privileged pod → no detections.
  - `test_batch_split_does_not_change_output`: generate seed 1 with the simulator, normalize,
    then compare one `process(all)` against `process` per single event into the same in-memory
    state. Assets, detections and incidents must be identical. This is a dev-only test dependency
    on the simulator; detection-core's dev group gets it (workspace), the runtime does not.
  - `test_rule_exception_is_isolated`: a rule whose `matches` raises on one event → other
    detections still produced, `rule_errors == 1`.

- [ ] **Step 2: Run the tests and confirm they fail.** Implement, re-run, and commit:
      `feat(detection): pipeline that enriches, matches, correlates and scores a batch`

### Task 7: Worker: store and detect in one transaction

**Files:**

- Create:
  - `apps/api/migrations/versions/0003_detection_tables.py`
  - `apps/api/src/ephoros_api/adapters/db/detection.py`
- Modify:
  - `apps/api/src/ephoros_api/adapters/db/tables.py` (`assets`, `identities`, `detections`,
    `incidents`, `incident_detections`)
  - `apps/api/src/ephoros_api/domain/ports.py`
  - `apps/api/src/ephoros_api/services/ingest.py`
  - `apps/api/src/ephoros_api/entrypoints/worker.py`
  - `apps/api/tests/test_ingest_service.py` (fakes)
  - `apps/api/tests/integration/conftest.py` (the TRUNCATE list)
- Test: `apps/api/tests/integration/test_detection_store.py`

**Interfaces:**

- **Port, in `ports.py`:**
  ```python
  class DetectionTx(StateView, Protocol):
      async def add_events(self, events: Sequence[Event]) -> list[Event]  # inserted only (RETURNING)
      async def apply(self, changes: Changes) -> None
  class DetectionStore(Protocol):
      def transaction(self) -> AbstractAsyncContextManager[DetectionTx]
  ```
- **`IngestService`:**
  - `__init__(store: DetectionStore, bus, pipeline: DetectionPipeline, now=...)`
  - `_store` per batch: `async with store.transaction() as tx:`, then
    `inserted = await tx.add_events(batch)`, then
    `await tx.apply(await pipeline.process(inserted, tx))`
  - the row-by-row fallback keeps its behaviour, with each row in its own transaction
  - `IngestResult` gains `detections: int` and `rule_errors: int`
- **Tables:**
  - `incidents`: `incident_id` pk, `status` default `open`, `risk_score` real, `raised` bool,
    `score_breakdown` jsonb, `mitre` text[], `first_seen`, `last_seen`, `entity_keys` text[]
    (GIN index), `created_at`, `updated_at`
  - `detections`: the `Detection` fields, plus `detected_at`
  - `incident_detections(incident_id, detection_id)` pk on both
  - merging re-points the join rows and deletes merged-away incidents
- **Worker:**
  - builds `DetectionPipeline(load_rules(), DetectionConfig())` at start; an invalid rule exits
    non-zero with the `RuleError` message
  - add `# shortcut: one worker consumer only, partition the stream by principal/asset before
running worker ×N (M8 Helm)` in `worker.py`

- [ ] **Step 1: Write the failing tests (integration, Testcontainers)**
  - `test_events_and_detections_commit_together`: make `apply` raise → no new rows in `events` or
    `detections`.
  - `test_redelivered_batch_creates_no_duplicate_detections`: handle the same batch twice → the
    detection count is unchanged, and `IngestResult.duplicates` equals the batch size.
  - `test_state_round_trips`: `apply` an asset, identity and incident → read back through the
    `StateView` methods unchanged.
  - Unit: update `test_ingest_service.py` fakes to the new port; existing behaviours stay green.

- [ ] **Step 2: Run the tests and confirm they fail.** Implement, then run
      `uv run pytest apps/api/tests -q` (Docker up). Expected: PASS. Then
      `uv run lint-imports && uv run mypy`.

- [ ] **Step 3: Commit**
      `feat(api): detect inside the worker's store transaction`

### Task 8: `GET /api/v1/incidents` and `GET /api/v1/incidents/{id}`

**Files:**

- Create: `apps/api/src/ephoros_api/api/v1/incidents.py`, `apps/api/src/ephoros_api/adapters/db/incidents.py`
- Modify:
  - `apps/api/src/ephoros_api/app.py` (router and `app.state.incident_store`)
  - `apps/api/src/ephoros_api/domain/ports.py` (`IncidentStore`)
  - `libs/shared/api-contract/openapi.json` and `src/generated/**` (regenerated)
- Test: `apps/api/tests/test_incidents_api.py`, `apps/api/tests/integration/test_incident_store.py`

**Interfaces:**

- **Router:** `APIRouter(prefix="/api/v1", tags=["incidents"], dependencies=[Depends(current_user)])`.
- **Dependency alias:** `IncidentStoreDep`, in the same style as `EventStoreDep`.
- **Models:**
  - `IncidentSummary`: incident_id, risk_score, raised, status, mitre, first_seen, last_seen,
    detection_count, asset_count, identity_count
  - `IncidentPage`: items, next_cursor
  - `DetectionOut`: detector, title, severity, confidence, mitre, reason, observed_at, event_ids
  - `EvidenceEvent`: `EventOut` fields plus `raw`
  - `IncidentDetail`: summary fields, `score_breakdown: dict[str, Any]`, `detections`, `evidence`
    (up to 50, oldest first)
- **Endpoints:**
  - `list_incidents(store, limit: Annotated[int, Query(ge=1, le=200)] = 50, cursor: str | None = None, min_risk: Annotated[float, Query(ge=0, le=100)] = 0) -> IncidentPage`
    - newest first by `(last_seen, incident_id)` descending
    - the cursor encoding follows `events.py` (base64 of `iso|uuid`); a bad cursor → 400
  - `get_incident(incident_id: UUID, store) -> IncidentDetail`
    - unknown id → `HTTPException(404, "Incident not found")`, rendered as problem+json by the
      existing handlers
    - `responses={401: …, 404: …}` with the `Problem` model

- [ ] **Step 1: Write the failing tests**
  - `test_incidents_require_auth`: the existing guard test covers it automatically. Confirm it
    lists the 2 new operations.
  - `test_list_is_newest_first_and_pages`
  - `test_bad_cursor_is_400`
  - `test_min_risk_filters`
  - `test_detail_has_breakdown_detections_and_raw_evidence`
  - `test_unknown_incident_is_404_problem`
  - `test_evidence_capped_at_50`

- [ ] **Step 2: Run the tests and confirm they fail.** Implement, then run `just check-contract`
      (regenerates the client). Expected: the only diff is the new operations. Commit the generated
      files with the code.

- [ ] **Step 3: Commit**
      `feat(api): list and inspect incidents with score breakdown and evidence`

### Task 9: `ephoros_eval`: matching, metrics, report (pure), leakage guard

**Files:**

- Create:
  - `libs/py/evaluation/{pyproject.toml,project.json}`
  - `libs/py/evaluation/src/ephoros_eval/{__init__,targets,metrics,report}.py`
  - `libs/py/evaluation/tests/{test_metrics,test_report,test_leakage}.py`
- Modify: root `pyproject.toml` (workspace member, mypy `files`, isort known-first-party,
  pytest `pythonpath`), `.importlinter`, `uv.lock`

**Interfaces:**

```python
# metrics.py
@dataclass(frozen=True) class LabelRow: scenario: str; variant: str; is_malicious: bool
    severity: Severity; instance_id: str; asset_class: str | None
@dataclass(frozen=True) class IncidentRow: incident_id: UUID; first_seen: datetime; raised: bool
    risk_score: float; mitre: list[str]; event_ids: list[UUID]
@dataclass(frozen=True) class RunOutput: incidents: list[IncidentRow]; detection_count: int
    asset_classes: dict[str, str]; asset_events: dict[str, list[UUID]]; rule_errors: int
Status = Literal["pass", "fail", "not_measured"]
@dataclass(frozen=True) class MetricResult: key: str; name: str; value: float | None
    target: str; status: Status; note: str
def match(incidents, labels: Mapping[UUID, LabelRow]) -> dict[UUID, str]   # incident → instance id
def evaluate(out: RunOutput, labels, targets, reference: Mapping[str, str]) -> list[MetricResult]
def per_variant(out, labels) -> list[VariantRow]  # instances, caught, missed ids, false positives
# report.py
def render(header: Mapping[str, str], results, variants, false_positives, ablation) -> str
def summary_table(results) -> str  # the pass / fail / not-measured table for $GITHUB_STEP_SUMMARY
```

**Metric definitions (copy exactly from the design §6.9, decided):**

- **Matching:**
  - `match` uses only labelled events
  - majority instance; ties go to the lower instance id
- **True and false positives:**
  - one true positive per malicious instance, the earliest by `(first_seen, incident_id)`
  - every other raised incident is a false positive
- **Precision and recall:**
  - precision = TP ÷ raised incidents
  - recall = caught ÷ malicious instances
- **Noise reduction:**
  - `1 − raised ÷ detection_count`
  - the all-incidents figure is reported in the note
- **Legit-burst suppression:**
  - a burst is a `legit_burst` instance
  - it is not suppressed if any raised incident contains any of its events
- **Purity:** the mean over raised incidents of the matched instance's share.
- **Spearman:** `statistics.correlation(risk, severity_ordinal, method="ranked")` over all matched
  incidents, raised or not; fewer than 3 incidents → fail.
- **Ephemeral recall:**
  - each asset's truth is the majority of its events' non-null `asset_class`
  - recall = ephemeral truths classified ephemeral ÷ ephemeral truths
- **MITRE:**
  - `reference = {"miner": "T1496", "debug_service": "T1190", "stolen_human": "T1078"}`, by
    variant
  - each reference variant's first caught instance's incident must contain the technique
  - the score is `n/3`, and it passes only at 3/3
- **Not measured:** latency and narrative validity are always `not_measured`, with a note. The
  ablation rows L1+L2 and L1+L2+L3 are `not_measured`.
- **No data:** any value that can't be computed (zero denominators) → `value=None`,
  `status="fail"`, with a note saying why.

**import-linter contract `labels-never-reach-detection`:** forbidden, from source modules
`ephoros_detection` and `ephoros_api` to `ephoros_sim` and `ephoros_eval`. Add `ephoros_sim` and
`ephoros_eval` to `root_packages`.

- [ ] **Step 1: Write the failing tests**
  - `test_duplicate_alerts_count_one_tp_rest_fp`
  - `test_lookalike_alert_is_fp`
  - `test_burst_touched_by_raised_incident_is_not_suppressed`
  - `test_noise_uses_raised_and_notes_all`
  - `test_purity_mean_of_matched_share`
  - `test_spearman_ranked`
  - `test_ephemeral_recall_majority_truth`
  - `test_mitre_three_of_three`
  - `test_empty_inputs_fail_not_pass`
  - `test_not_measured_never_fails`
  - `test_report_lists_misses_and_false_positives_by_id`
  - `test_only_eval_and_sim_mention_event_labels`: grep `apps/api/src` and
    `libs/py/detection-core/src` for `event_labels`. The only allowed hit is the `tables.py`
    definition, which the migrations need; it carries a comment saying it is read only by the
    evaluation.

- [ ] **Step 2: Run the tests and confirm they fail.** Implement, then run
      `uv run pytest libs/py/evaluation -q && uv run lint-imports && uv run mypy`. Expected: PASS.

- [ ] **Step 3: Commit**
      `feat(eval): strict incident matching, challenge metrics and the report renderer`

### Task 10: `ephoros-eval run` and `just evaluate`: real worker on throwaway stores

**Files:**

- Create:
  - `libs/py/evaluation/src/ephoros_eval/{run,collect,cli}.py`
  - `libs/py/evaluation/tests/integration/test_run.py`
  - `docs/evaluation/.gitkeep`
- Modify: `justfile`

**Interfaces:**

- **`cli.main(argv) -> int`:**
  - `ephoros-eval run [--seed 20261029] [--note TEXT] [--out docs/evaluation]`
  - returns 0, 1 or 2 as in Global Constraints; any exception → print it and return 2
- **`run.evaluate(seed, start, out_dir, note) -> EvalResult`:**
  1. Start `PostgresContainer("postgres:17.11-alpine", driver=None)` and
     `RedisContainer("redis:7.4.11-alpine")`, and run Alembic `upgrade head` (as in the
     integration conftest).
  2. Start the worker with `subprocess.Popen([shutil.which("ephoros-worker")], env=...)`, using
     `DATABASE_URL`, `REDIS_URL`, `APP_ENV=dev`, `JWKS_URL=http://unused.invalid/jwks` and
     `JWT_ISSUER=unused`.
  3. Write labels and publish the warm-up (run_id `warmup-<seed>`), then the labelled window
     (run_id `seed<seed>`), with `ephoros_sim.labels.write_labels` and `ephoros_sim.replay.publish`.
  4. Drain: poll every 0.5 s until `XLEN events.raw == 0` and the group's pending count is 0,
     with a 300 s timeout. A timeout, or the worker process exiting, means exit 2.
  5. Terminate the worker with SIGTERM.
- **`collect.read(dsn, run_id) -> tuple[RunOutput, dict[UUID, LabelRow]]`:**
  - asyncpg queries over the core tables
  - incidents included are those with at least one event from the labelled run
  - `rule_errors` come from the worker log lines; the worker logs
    `ingested batch: IngestResult(...)`, and these are summed
- **Outputs:**
  - `docs/evaluation/report.md` (overwritten)
  - `docs/evaluation/summary.md` (status table only, used by CI, git-ignored)
  - one appended line in `docs/evaluation/runs.jsonl`: `{ts, seed, commit, dirty, metrics: {key: value}, statuses, note}`
  - header fields: seed, warm-up seed, simulator version, dataset sha256 (same `dump` as the
    golden test), git commit (and dirty flag), rule ids@versions, `DetectionConfig` as JSON, run
    time
- **`justfile`:**

  ```
  # replay a labelled dataset through the real worker and write docs/evaluation/report.md
  evaluate seed="20261029" note="":
      uv run --package ephoros-eval ephoros-eval run --seed {{seed}} --note "{{note}}"
  ```

- [ ] **Step 1: Write the failing tests (integration, Docker)**
  - `test_run_is_deterministic`: two `evaluate(seed=1, …)` runs into tmp dirs → identical
    `metrics` and statuses.
  - `test_drain_timeout_is_exit_2`: with the worker command replaced by `sleep 600` and a 3 s
    timeout, `main` returns 2.
  - `test_report_header_records_reproducibility_fields`.

- [ ] **Step 2: Run the tests and confirm they fail.** Implement, then run `just evaluate 1` by
      hand. Expected: a report is written, and the exit code is 0 or 1, never 2.

- [ ] **Step 3: Commit**
      `feat(eval): just evaluate replays seeds through the real worker on throwaway stores`

### Task 11: Tune on dev seeds, publish the held-out report, hand over the CI job

**Files:**

- Modify (tuning only): `ephoros_detection/rules/builtin/*.yaml`, `ephoros_detection/config.py`
- Create: `docs/evaluation/report.md` (held-out), `docs/evaluation/runs.jsonl`, and
  `docs/adr/NNNN-*.md` only if a target stays missed
- Hand-over (not committed by the agent): the `.github/workflows/ci.yml` diff below

**Steps:**

- [ ] **Step 1: Baseline.** Run `just evaluate 1`, `2` and `3` with the note `baseline`, and commit
      `runs.jsonl`.
- [ ] **Step 2: Tune.** For each failing measured metric, look at the listed false positives and
      misses in the **dev** reports.
  - Make one defensible change per run: a rule condition, an `unless` with a written reason, or a
    weight. Bump the version of any rule you edit.
  - Re-run all three dev seeds with a note describing the change.
  - Keep a change only if recall does not drop on any dev seed while precision rises, or the
    reverse.
  - Commit each kept change together with its `runs.jsonl` lines:
    `tune(detection): <change> (dev seeds: P x→y, R x→y)`. Commitlint may need `tune` added. If it
    is not an allowed type, use `fix(detection)`.
- [ ] **Step 3: Held-out run.** Run `just evaluate` once, with the default held-out seed and the
      note `held-out`. Commit `report.md` and `runs.jsonl` as-is:
      `docs(eval): held-out M4 evaluation report`.
  - **Never tune after looking at this run.** If a further change is needed, it goes back through
    step 2 on the dev seeds.
- [ ] **Step 4: Misses.** For each measured target still missed, write an ADR in `docs/adr/`
      covering:
  - the metric, its value and its target
  - what was tried, with the run lines
  - why it misses
  - the proposal: a fix in M6, or a recalibration

  It stays `Status: proposed` until the owner approves it.

- [ ] **Step 5: CI hand-over.** Give the owner this job to add to `.github/workflows/ci.yml`.
  - It goes after `e2e`, and its setup steps are copied from the `checks` job.
  - It is report-only during M4. Exit 1 is allowed but loud, and exit 2 fails the job.
  - When every measured target passes, delete the `if [ "$code" -eq 1 ]` line so the job becomes
    blocking.

  ```yaml
  evaluate:
    needs: checks
    runs-on: ubuntu-latest
    steps:
      # checkout, mise-action, cache, uv sync --frozen --all-packages: same as `checks`
      - name: Evaluate the held-out seed (report-only during M4)
        run: |
          set +e
          just evaluate
          code=$?
          cat docs/evaluation/summary.md >> "$GITHUB_STEP_SUMMARY"
          if [ "$code" -eq 1 ]; then echo "::warning::measured M4 targets missed, see the job summary"; exit 0; fi
          exit "$code"
      - if: always()
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: evaluation-report
          path: docs/evaluation/
  ```

- [ ] **Step 6: Milestone close.**
  - Lint, typecheck, test and build for all projects (`pnpm nx run-many -t lint typecheck test
build`), plus `just check-contract` and `just e2e`.
  - Then a fresh whole-branch review → ponytail-debt → finishing-a-development-branch.
  - Update memory: M4 status, and the held-out seed rule.
