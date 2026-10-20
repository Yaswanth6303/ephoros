# Milestone 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A cloned repo runs `just setup && just certs && just up` and serves, over HTTPS through
Traefik, an Angular page that reads FastAPI's health through a generated TypeScript client, with
Postgres and Redis behind a real readiness check, and CI enforcing all of it.

**Architecture:** One Nx integrated monorepo (pnpm, single root `package.json`) holds the Angular
app, the Playwright project and the generated API-contract library; one uv workspace holds the
FastAPI package `ephoros-api`, wired into Nx through `nx:run-commands`. Docker Compose runs
Traefik (file provider, mkcert TLS) in front of `web` (nginx) and `api` (uvicorn), with Postgres
and Redis. `just` is the only human entrypoint.

**Tech Stack:** mise · just · pnpm · Nx 23.3 · Angular 22.2 (zoneless, Vitest) · Tailwind v4 ·
hey-api openapi-ts (Angular client) · Playwright · uv · Python 3.13 · FastAPI 0.150 · asyncpg ·
redis-py · Docker Compose · Traefik v3.7 · Postgres 17 · Redis 7.4 · GitHub Actions · lefthook.

**Spec:** `docs/superpowers/specs/2026-10-10-ephoros-design.md` (§3, §4, §9.4, §11, §12, §14, §16, §17.1).

## Global Constraints

- Versions (verified 2026-10-20 against npm/PyPI/Docker Hub), pinned exactly:
  node `24.22.0`, pnpm `12.14.0`, python `3.13.16`, uv `0.13.3`, just `1.59.0`, mkcert `1.4.4`,
  gitleaks `8.30.1`, lefthook `2.2.2` (all in `mise.toml`); nx/@nx/* `23.3.0`; @angular/* `22.2.3`;
  **typescript `~6.0.3`** (Angular 22 peer range is `>=6.0 <6.1` — never accept TS 7);
  tailwindcss + @tailwindcss/postcss `4.3.3`; @hey-api/openapi-ts `0.99.0`; @playwright/test `1.64.1`;
  fastapi `0.150.0`; uvicorn `0.54.0`; pydantic-settings `2.16.0`; asyncpg `0.32.0`; redis `8.1.0`;
  pytest `9.1.1`; httpx `0.28.1`; ruff `0.17.1`; mypy `2.4.0`; images `traefik:v3.7.15`,
  `postgres:17.11-alpine`, `redis:7.4.11-alpine`, `nginxinc/nginx-unprivileged` (stable-alpine).
- just is the front door → Nx orchestrates → uv/pnpm manage packages → mise pins versions (spec §4.1).
  Every just recipe is a one-line delegation; no logic in the justfile.
- FastAPI: `lifespan=` only (no `@app.on_event`, deprecated); async tests use
  `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` with
  `@pytest.mark.anyio` (FastAPI docs, "Async Tests").
- All API routes live under `/api/v1`. Operation IDs = route function names
  (`generate_unique_id_function=lambda route: route.name`) so the SDK exposes `healthz()`, `readyz()`.
- Errors are RFC 9457 `application/problem+json` (spec §9.4). `trace_id` arrives with OTel in M9.
- Angular: standalone + zoneless (default in v21+, no zone.js, no `provideZoneChangeDetection`);
  unit tests via `@angular/build:unit-test` (Vitest, Nx `--unitTestRunner=vitest-angular`);
  new-style file names (`status.ts`, not `status.component.ts`).
- Nx tags per spec §4.3: `type:app|feature|data-access|ui|util|contract`, `scope:web|shared|py`.
- Local origin: `https://ephoros.localhost` (Traefik, mkcert cert). Secrets never committed;
  `.env.example` holds dev-only defaults; `.env` and `infra/traefik/certs/` are git-ignored.
- Out of scope for M1 (later milestones own them): auth service and Spartan/cn (M2), Alembic and
  SQLAlchemy (M3), structlog (M3), kubectl/kind/helm pins (M8), OTel/Prometheus (M9), Playwright
  multi-browser + sharding (M9), GHCR push needs a GitHub remote (workflow written now, runs once pushed).

### Per-task workflow (Superpowers + Ponytail, applies to every task)

1. superpowers:test-driven-development — write the failing test, watch it fail.
2. ponytail (full) — smallest code that passes; no unrequested options/abstractions.
3. superpowers:verification-before-completion — run the task's verify commands, read the output.
4. ponytail:ponytail-review on the task diff — fix findings.
5. Commit (Conventional Commits). Deliberate limits get `# shortcut: <limit>, <upgrade path>`.

Milestone end: superpowers:requesting-code-review (ponytail-review checklist) → ponytail:ponytail-debt
→ superpowers:finishing-a-development-branch.

## Review Focus

1. **Postgres or Redis hangs (not refuses)** — `/readyz` must answer 503 within ~2 s, never hang the
   probe. Test in Task 4: `test_readyz_times_out_slow_dependency`.
2. **A check raises an unexpected exception type** (`OSError`, `ConnectionRefusedError`, asyncpg
   error) — 503 with that check marked failed, never a 500, never leaking DSNs/hosts in the body.
   Tests in Task 4: `test_readyz_reports_failed_dependency`, `test_readyz_hides_error_details`.
3. **API changed but client not regenerated** — CI must fail. Verify step in Task 7 deliberately
   creates drift and watches `just check-contract` fail.
4. **API down while web is up** — the page must say `API: unreachable`, not stay blank or throw.
   Test in Task 7: `shows unreachable when the API fails`.
5. **SPA fallback swallowing API paths** — `https://ephoros.localhost/api/v1/healthz` must return
   API JSON, and an unknown `/api/v1/x` must return problem+json 404 from FastAPI, not `index.html`.
   Playwright test in Task 8: `unknown API path is a problem+json 404`.

---

### Task 1: Toolchain root (mise, just, git hygiene)

**Files:**
- Create: `mise.toml`, `justfile`, `.gitignore`, `.editorconfig`, `.env.example`

**Interfaces:**
- Produces: `just setup` (later tasks extend it); env vars `POSTGRES_PASSWORD`, `DATABASE_URL`,
  `REDIS_URL`, `APP_ENV` documented in `.env.example`.

- [ ] **Step 1: Create `mise.toml`** with `[tools]` pinned to the versions in Global Constraints and
  `[env] _.file = ".env"`.
- [ ] **Step 2: Create `.env.example`:**
  ```dotenv
  APP_ENV=dev
  POSTGRES_PASSWORD=ephoros-dev-only
  DATABASE_URL=postgresql://ephoros:ephoros-dev-only@localhost:5432/ephoros
  REDIS_URL=redis://localhost:6379/0
  ```
- [ ] **Step 3: Create `.gitignore`** covering `.env`, `node_modules/`, `dist/`, `.nx/`, `.venv/`,
  `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `coverage/`, `test-results/`,
  `playwright-report/`, `infra/traefik/certs/`, `.DS_Store`, and the pre-existing local tool dirs
  `.claude-flow/`, `.swarm/`, `ruvector.db`.
- [ ] **Step 4: Create `justfile`** with `set dotenv-load := false` (mise loads env), a default recipe
  `@just --list`, and `setup: mise install` (Tasks 2 and 3 append `pnpm install` / `uv sync`).
- [ ] **Step 5: Verify**
  Run: `cp -n .env.example .env; mise install && mise current && just --list`
  Expected: every tool reports the pinned version; just lists `setup`.
- [ ] **Step 6: Commit** — `chore: pin toolchain with mise and add justfile`

---

### Task 2: Nx + pnpm workspace root

**Files:**
- Create: `package.json`, `pnpm-workspace.yaml`, `nx.json`, `tsconfig.base.json`, `.prettierrc`,
  `.prettierignore`, `eslint.config.mjs`
- Modify: `justfile` (`setup` gains `pnpm install`)

**Interfaces:**
- Produces: `pnpm nx …` works; plugins `@nx/angular`, `@nx/js`, `@nx/playwright`, `@nx/eslint`
  installed at `23.3.0`; `tsconfig.base.json` `compilerOptions.paths` (filled by Task 7).

- [ ] **Step 1: Generate a reference workspace in the scratchpad** (not in the repo):
  `pnpm dlx create-nx-workspace@23.3.0 ephoros --preset=apps --pm=pnpm --workspaces=false --nxCloud=skip --skipGit --formatter=prettier --linter=eslint --aiAgents=none --interactive=false`.
  `--workspaces=false` gives the integrated layout (tsconfig paths + `project.json`), which Angular needs.
- [ ] **Step 2: Copy its root files into the repo** (list above), set `"name": "ephoros"`,
  `"private": true`, `"packageManager": "pnpm@12.14.0"`, `"engines": {"node": ">=24.22.0"}`.
  `pnpm-workspace.yaml` holds `packages: []` plus pnpm settings only.
- [ ] **Step 3: Add plugins and pin TypeScript**
  Run: `pnpm nx add @nx/angular@23.3.0 && pnpm nx add @nx/playwright@23.3.0 && pnpm add -D typescript@~6.0.3`
- [ ] **Step 4: Verify** — Run: `pnpm nx report`
  Expected: all `@nx/*` at 23.3.0, `typescript 6.0.x`, no peer-dependency warnings for TS.
- [ ] **Step 5: Commit** — `chore: add Nx 23 integrated workspace with pnpm`

---

### Task 3: Python uv workspace and FastAPI `/healthz`

**Files:**
- Create: `pyproject.toml` (root: `[tool.uv.workspace] members = ["apps/api"]`, dev dependency group,
  ruff/mypy/pytest config), `apps/api/pyproject.toml`,
  `apps/api/src/ephoros_api/__init__.py`, `apps/api/src/ephoros_api/config.py`,
  `apps/api/src/ephoros_api/app.py`, `apps/api/src/ephoros_api/api/__init__.py`,
  `apps/api/src/ephoros_api/api/v1/__init__.py`, `apps/api/src/ephoros_api/api/v1/health.py`,
  `apps/api/src/ephoros_api/entrypoints/__init__.py`, `apps/api/src/ephoros_api/entrypoints/api.py`
- Test: `apps/api/tests/conftest.py`, `apps/api/tests/test_health.py`
- Modify: `justfile` (`setup` gains `uv sync --all-packages`)

**Interfaces:**
- Produces:
  - `class Settings(BaseSettings)`: `app_env: Literal["dev","e2e","prod"] = "dev"`,
    `database_url: str`, `redis_url: str`, `readiness_timeout_s: float = 2.0`.
  - `def create_app(settings: Settings | None = None) -> FastAPI` in `ephoros_api/app.py`
    (`title="Ephoros API"`, `version="0.1.0"`, `generate_unique_id_function=lambda r: r.name`,
    stores `app.state.settings = settings`; `lifespan=` placeholder that yields).
  - `router = APIRouter(prefix="/api/v1", tags=["ops"])` in `api/v1/health.py`;
    `class Health(BaseModel): status: Literal["ok"]`; `async def healthz() -> Health`.
  - `ephoros_api.entrypoints.api:app` (module-level `app = create_app()`).
  - Pytest fixture `client` (AsyncClient over ASGITransport) and `settings` (dummy URLs) in `conftest.py`.

- [ ] **Step 1: Write the failing test** `apps/api/tests/test_health.py`
  ```python
  import pytest

  @pytest.mark.anyio
  async def test_healthz_is_ok(client):
      r = await client.get("/api/v1/healthz")
      assert r.status_code == 200
      assert r.json() == {"status": "ok"}

  @pytest.mark.anyio
  async def test_operation_ids_are_function_names(client):
      spec = (await client.get("/openapi.json")).json()
      assert spec["paths"]["/api/v1/healthz"]["get"]["operationId"] == "healthz"
  ```
  `conftest.py` also defines `anyio_backend` returning `"asyncio"`.
- [ ] **Step 2: Run** — `uv run pytest apps/api/tests -q` → FAIL (`ModuleNotFoundError: ephoros_api`).
- [ ] **Step 3: Implement** the files above. `apps/api/pyproject.toml`: name `ephoros-api`,
  `requires-python = ">=3.13"`, deps `fastapi==0.150.0`, `uvicorn[standard]==0.54.0`,
  `pydantic-settings==2.16.0`, `asyncpg==0.32.0`, `redis==8.1.0`; build backend `uv_build`; `src/` layout.
  Root dev group: `pytest==9.1.1`, `httpx==0.28.1`, `ruff==0.17.1`, `mypy==2.4.0`, `asyncpg-stubs`.
  Ruff: `line-length = 100`, `target-version = "py313"`, `select = ["E","F","I","B","UP","ASYNC"]`.
  Mypy: `strict = true`, `files = ["apps/api/src"]`, `plugins = ["pydantic.mypy"]`.
- [ ] **Step 4: Run** — `uv sync --all-packages && uv run pytest apps/api/tests -q` → 2 passed;
  `uv run ruff check . && uv run ruff format --check . && uv run mypy` → clean.
- [ ] **Step 5: Commit** — `feat(api): add FastAPI app factory with /api/v1/healthz`

---

### Task 4: `/readyz` with concurrent, time-boxed dependency checks + problem+json errors

**Files:**
- Create: `apps/api/src/ephoros_api/api/problems.py`, `apps/api/src/ephoros_api/adapters/__init__.py`,
  `apps/api/src/ephoros_api/adapters/health.py`
- Modify: `apps/api/src/ephoros_api/api/v1/health.py`, `apps/api/src/ephoros_api/app.py`
- Test: `apps/api/tests/test_readiness.py`, `apps/api/tests/test_problems.py`

**Interfaces:**
- Consumes: `create_app`, `Settings`, `router` (Task 3).
- Produces:
  - `Check = Callable[[], Awaitable[None]]`; `def get_checks(request: Request) -> dict[str, Check]`
    (FastAPI dependency, reads `request.app.state.checks`; tests override it).
  - `adapters/health.py`: `async def ping_postgres(dsn: str) -> None` (asyncpg connect,
    `SELECT 1`, close) and `async def ping_redis(url: str) -> None` (`redis.asyncio.from_url`, `ping`, `aclose`).
  - `lifespan` sets `app.state.checks` (httpx `AsyncClient` does not run lifespan, so tests always override `get_checks`): `app.state.checks = {"postgres": partial(ping_postgres, s.database_url), "redis": partial(ping_redis, s.redis_url)}`.
  - `class Readiness(BaseModel): status: Literal["ok"]; checks: dict[str, str]`;
    `async def readyz(...) -> Readiness`, documented `503` response with `Problem`.
  - `problems.py`: `class Problem(BaseModel)` (`type="about:blank"`, `title`, `status`, `detail`,
    plus extra fields allowed), `def problem_response(status: int, detail: str, **extra) -> JSONResponse`
    (media type `application/problem+json`), `def install_problem_handlers(app: FastAPI) -> None`
    for `StarletteHTTPException` and `RequestValidationError` (422, `errors` field).

- [ ] **Step 1: Write the failing tests** `apps/api/tests/test_readiness.py`
  ```python
  import asyncio, time, pytest
  from ephoros_api.api.v1.health import get_checks

  async def ok() -> None: ...
  async def refused() -> None: raise ConnectionRefusedError("postgres://ephoros:secret@db:5432")
  async def hangs() -> None: await asyncio.sleep(30)

  def use(app, checks): app.dependency_overrides[get_checks] = lambda: checks

  @pytest.mark.anyio
  async def test_readyz_all_ok(app, client):
      use(app, {"postgres": ok, "redis": ok})
      r = await client.get("/api/v1/readyz")
      assert r.status_code == 200
      assert r.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}

  @pytest.mark.anyio
  async def test_readyz_reports_failed_dependency(app, client):
      use(app, {"postgres": refused, "redis": ok})
      r = await client.get("/api/v1/readyz")
      assert r.status_code == 503
      assert r.headers["content-type"] == "application/problem+json"
      body = r.json()
      assert body["status"] == 503 and body["title"] == "Service Unavailable"
      assert body["checks"] == {"postgres": "fail: ConnectionRefusedError", "redis": "ok"}

  @pytest.mark.anyio
  async def test_readyz_hides_error_details(app, client):
      use(app, {"postgres": refused, "redis": ok})
      assert "secret" not in (await client.get("/api/v1/readyz")).text

  @pytest.mark.anyio
  async def test_readyz_times_out_slow_dependency(app, client):
      use(app, {"postgres": hangs, "redis": hangs})
      start = time.monotonic()
      r = await client.get("/api/v1/readyz")
      assert r.status_code == 503
      assert r.json()["checks"] == {"postgres": "fail: TimeoutError", "redis": "fail: TimeoutError"}
      assert time.monotonic() - start < 3.0  # checks run concurrently, readiness_timeout_s = 2.0
  ```
  `test_problems.py`:
  ```python
  @pytest.mark.anyio
  async def test_unknown_route_is_problem_json(client):
      r = await client.get("/api/v1/does-not-exist")
      assert r.status_code == 404
      assert r.headers["content-type"] == "application/problem+json"
      assert r.json()["status"] == 404
  ```
  Add an `app` fixture to `conftest.py` (`create_app(settings)`), and make `client` use it.
- [ ] **Step 2: Run** — `uv run pytest apps/api/tests -q` → FAIL (`ImportError: get_checks`).
- [ ] **Step 3: Implement.** `readyz` runs every check with
  `asyncio.gather(*(asyncio.wait_for(c(), settings.readiness_timeout_s) for c in checks.values()), return_exceptions=True)`;
  a result that is an `Exception` maps to `f"fail: {type(exc).__name__}"` (class name only — no message,
  so DSNs never leak). Settings reach the route via a `get_settings` dependency reading `app.state.settings`.
- [ ] **Step 4: Run** — `uv run pytest apps/api/tests -q` → 7 passed; ruff + mypy clean.
- [ ] **Step 5: Commit** — `feat(api): add /readyz with time-boxed dependency checks and problem+json errors`

---

### Task 5: Nx targets for the API + OpenAPI export + dev recipes

**Files:**
- Create: `apps/api/project.json`, `apps/api/src/ephoros_api/openapi.py`
- Test: `apps/api/tests/test_openapi_export.py`
- Modify: `justfile` (`test`, `lint`, `typecheck`, `fmt`)

**Interfaces:**
- Consumes: `create_app` (Task 3).
- Produces:
  - `def export_openapi(path: Path) -> None` + `if __name__ == "__main__"` CLI taking the output path;
    writes `json.dumps(spec, indent=2, sort_keys=True) + "\n"` (byte-stable for drift checks).
  - Nx project `api` (tags `type:app,scope:py`) targets, all `nx:run-commands` with `cwd` = workspace root:
    `serve` → `uv run uvicorn ephoros_api.entrypoints.api:app --reload --port 8000`;
    `test` → `uv run pytest apps/api/tests -q`; `lint` → `uv run ruff check apps/api && uv run ruff format --check apps/api`;
    `typecheck` → `uv run mypy`; `openapi` → `uv run python -m ephoros_api.openapi libs/shared/api-contract/openapi.json`
    (`outputs: ["{workspaceRoot}/libs/shared/api-contract/openapi.json"]`, `inputs` = api sources, cached).

- [ ] **Step 1: Write the failing test**
  ```python
  from ephoros_api.openapi import export_openapi

  def test_export_is_byte_stable(tmp_path):
      a, b = tmp_path / "a.json", tmp_path / "b.json"
      export_openapi(a); export_openapi(b)
      assert a.read_bytes() == b.read_bytes()
      assert '"operationId": "readyz"' in a.read_text()
  ```
  `export_openapi` must not require env vars: it calls `create_app(Settings(database_url="unused", redis_url="unused"))`.
- [ ] **Step 2: Run** — `uv run pytest apps/api/tests/test_openapi_export.py -q` → FAIL (ImportError).
- [ ] **Step 3: Implement** `openapi.py` and `apps/api/project.json`; add just recipes
  `test`/`lint`/`typecheck` → `pnpm nx run-many -t <target>` and `fmt` → `uv run ruff format . && pnpm nx format:write`.
- [ ] **Step 4: Verify** — `pnpm nx run-many -t test lint typecheck -p api` → all succeed;
  run it again → `[existing outputs match the cache]` for each target.
- [ ] **Step 5: Commit** — `build(api): wire Python targets into Nx and add OpenAPI export`

---

### Task 6: Angular 22 app shell + Tailwind v4 + module boundaries

**Files:**
- Create (generated, then trimmed): `apps/web/**`, `apps/web-e2e/**`, `apps/web/.postcssrc.json`,
  `apps/web/proxy.conf.json`
- Modify: `apps/web/src/styles.css`, `apps/web/project.json` (serve `proxyConfig`),
  `eslint.config.mjs` (`depConstraints`), `justfile` (`dev`)

**Interfaces:**
- Produces: Nx projects `web` (tags `type:app,scope:web`, prefix `eph`) and `web-e2e`;
  `appConfig` in `apps/web/src/app/app.config.ts` (Task 7 adds providers);
  `routes` in `apps/web/src/app/app.routes.ts`.

- [ ] **Step 1: Generate**
  Run: `pnpm nx g @nx/angular:application apps/web --prefix=eph --style=css --bundler=esbuild --unitTestRunner=vitest-angular --e2eTestRunner=playwright --routing --tags=type:app,scope:web --no-interactive`
  Confirm: no `zone.js` in `package.json` or `polyfills`; `test` target uses `@angular/build:unit-test`.
- [ ] **Step 2: Tailwind v4** — `pnpm add -D tailwindcss@4.3.3 @tailwindcss/postcss@4.3.3 postcss`;
  `.postcssrc.json` = `{"plugins":{"@tailwindcss/postcss":{}}}`; `styles.css` starts with `@import "tailwindcss";`.
  Replace the generated welcome component template with a `<main class="p-6"><router-outlet/></main>` shell;
  delete the generated welcome component/test files.
- [ ] **Step 3: Dev proxy** — `proxy.conf.json` = `{"/api": {"target": "http://localhost:8000", "secure": false}}`,
  referenced from `web:serve` options. `just dev` → `docker compose up -d postgres redis && pnpm nx run-many -t serve -p web api`.
- [ ] **Step 4: Module boundaries** — in `eslint.config.mjs` `@nx/enforce-module-boundaries.depConstraints`
  encode spec §4.3: `type:app` → `type:feature|data-access|ui|util|contract`; `type:feature` → `type:data-access|ui|util`;
  `type:data-access` → `type:contract|util`; `type:ui` → `type:util`; `type:contract` → none;
  `scope:web` → `scope:web|shared`; `scope:shared` → `scope:shared`.
- [ ] **Step 5: Verify** — `pnpm nx run-many -t lint test build -p web` → succeeds (generated app spec
  updated to assert the shell renders a `main` element).
- [ ] **Step 6: Commit** — `feat(web): scaffold zoneless Angular 22 app with Tailwind v4`

---

### Task 7: Generated API contract + status page (end-to-end type safety)

**Files:**
- Create: `libs/shared/api-contract/` (via `@nx/js:library`, then `openapi-ts.config.ts`,
  `src/index.ts` re-exporting `./generated`), `apps/web/src/app/status/status.ts`,
  `apps/web/src/app/status/status.spec.ts`
- Modify: `apps/web/src/app/app.config.ts`, `apps/web/src/app/app.routes.ts`, `.prettierignore`,
  `tsconfig.base.json` (path `@ephoros/api-contract`), `justfile` (`gen-client`, `check-contract`)

**Interfaces:**
- Consumes: Nx `api:openapi` target (Task 5).
- Produces:
  - Nx project `api-contract` (tags `type:contract,scope:shared`), target `generate`
    (`dependsOn: ["api:openapi"]`, runs `openapi-ts` in the lib dir). Config:
    `defineConfig({ input: './openapi.json', output: './src/generated', plugins: ['@hey-api/client-angular', '@hey-api/sdk'] })`
    from `@hey-api/openapi-ts`. Generated files are committed and prettier-ignored.
  - Import path `@ephoros/api-contract` exporting `healthz`, `readyz`, `client`, `provideHeyApiClient`, types `Health`, `Readiness`.
  - `appConfig.providers` includes `provideHttpClient(withFetch())` and `provideHeyApiClient(client)`.
  - `Status` component (selector `eph-status`, route `''`) rendering exactly `API: ok` or `API: unreachable`.

- [ ] **Step 1: Generate the lib and client**
  Run: `pnpm nx g @nx/js:library libs/shared/api-contract --bundler=none --unitTestRunner=none --tags=type:contract,scope:shared --importPath=@ephoros/api-contract --no-interactive && pnpm add -D @hey-api/openapi-ts@0.99.0`,
  add config + `project.json` target, then `pnpm nx run api-contract:generate`.
- [ ] **Step 2: Write the failing component test** `status.spec.ts`
  ```ts
  describe('Status', () => {
    beforeEach(() => TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideHeyApiClient(client)],
    }));

    // zoneless: the resource fires its request asynchronously, so poll for it
    const pending = () => vi.waitFor(() => TestBed.inject(HttpTestingController).expectOne('/api/v1/healthz'));

    it('shows ok when the API is healthy', async () => {
      const fixture = TestBed.createComponent(Status);
      (await pending()).flush({ status: 'ok' });
      await fixture.whenStable();
      expect(fixture.nativeElement.textContent).toContain('API: ok');
    });

    it('shows unreachable when the API fails', async () => {
      const fixture = TestBed.createComponent(Status);
      (await pending()).flush('bad gateway', { status: 502, statusText: 'Bad Gateway' });
      await fixture.whenStable();
      expect(fixture.nativeElement.textContent).toContain('API: unreachable');
    });
  });
  ```
- [ ] **Step 3: Run** — `pnpm nx test web` → FAIL (`Cannot find module './status'`).
- [ ] **Step 4: Implement** `Status` with a signal `resource({ loader: () => healthz({ throwOnError: true }) })`;
  template uses `@if` on `status.hasValue()` / `status.error()`. Wire route and providers.
- [ ] **Step 5: Run** — `pnpm nx test web` → passes; `pnpm nx lint web` → no boundary violations.
- [ ] **Step 6: Add recipes** — `gen-client` → `pnpm nx run api-contract:generate`;
  `check-contract` → `just gen-client && git diff --exit-code -- libs/shared/api-contract`.
- [ ] **Step 7: Verify drift detection (Review Focus 3)** — temporarily add `summary="x"` to the
  `healthz` decorator, run `just check-contract` → exits non-zero with a diff; revert, run again → exit 0.
- [ ] **Step 8: Commit** — `feat(contract): generate Angular API client from OpenAPI and show API status`

---

### Task 8: Containers, Compose, Traefik TLS, Playwright smoke

**Files:**
- Create: `apps/api/Dockerfile`, `apps/web/Dockerfile`, `apps/web/nginx.conf`, `.dockerignore`,
  `compose.yaml`, `infra/traefik/traefik.yml`, `infra/traefik/dynamic.yml`, `infra/postgres/init.sql`,
  `apps/web-e2e/src/smoke.spec.ts`
- Modify: `apps/web-e2e/playwright.config.ts`, `justfile` (`certs`, `up`, `down`, `logs`, `e2e`)
- Delete: generated `apps/web-e2e/src/example.spec.ts`

**Interfaces:**
- Consumes: `ephoros_api.entrypoints.api:app`, `web:build` output `dist/apps/web/browser`.
- Produces: `https://ephoros.localhost` serving web at `/` and api at `/api/v1/*`; recipes
  `just certs`, `just up`, `just down`, `just e2e`.

- [ ] **Step 1: Write the failing smoke test** `apps/web-e2e/src/smoke.spec.ts`
  ```ts
  import { test, expect } from '@playwright/test';

  test('status page shows the API is healthy', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('API: ok')).toBeVisible();
  });

  test('readiness sees postgres and redis', async ({ request }) => {
    const r = await request.get('/api/v1/readyz');
    expect(r.status()).toBe(200);
    expect((await r.json()).checks).toEqual({ postgres: 'ok', redis: 'ok' });
  });

  test('unknown API path is a problem+json 404', async ({ request }) => {
    const r = await request.get('/api/v1/nope');
    expect(r.status()).toBe(404);
    expect(r.headers()['content-type']).toBe('application/problem+json');
  });
  ```
  `playwright.config.ts`: `baseURL: process.env.E2E_BASE_URL ?? 'https://ephoros.localhost'`,
  `ignoreHTTPSErrors: true` (dev cert), Chromium only, remove the generated `webServer` block
  (Compose provides the stack), `trace: 'retain-on-failure'`.
- [ ] **Step 2: Run** — `pnpm nx e2e web-e2e` → FAIL (`net::ERR_CONNECTION_REFUSED`).
- [ ] **Step 3: Implement images.**
  - API: builder `python:3.13-slim` + `COPY --from=ghcr.io/astral-sh/uv:0.13.3 /uv /bin/uv`,
    `uv sync --frozen --no-dev --package ephoros-api --no-editable`; runtime `python:3.13-slim`,
    copy `.venv`, user `10001`, `CMD uvicorn ephoros_api.entrypoints.api:app --host 0.0.0.0 --port 8000 --proxy-headers`.
  - Web: builder `node:24.22.0-slim` with corepack pnpm, `pnpm install --frozen-lockfile`,
    `pnpm nx build web`; runtime `nginxinc/nginx-unprivileged:stable-alpine` on 8080, `nginx.conf`
    with `try_files $uri $uri/ /index.html` and long cache for hashed assets.
- [ ] **Step 4: Implement Compose + Traefik.**
  - `compose.yaml`: `traefik` (ports `80`,`443`; mounts `infra/traefik/*.yml` and `certs/` read-only;
    file provider only — no Docker socket), `web`, `api` (env `DATABASE_URL`/`REDIS_URL` pointing at
    service names, `APP_ENV`; healthcheck `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/healthz')"`;
    `depends_on` postgres/redis `service_healthy`), `postgres` (`POSTGRES_USER/DB=ephoros`,
    `POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?set in .env}`, `pg_isready` healthcheck, named volume,
    `127.0.0.1:5432:5432`, `init.sql` mounted to `/docker-entrypoint-initdb.d/`), `redis`
    (`redis-cli ping` healthcheck, `127.0.0.1:6379:6379`).
  - `traefik.yml`: entryPoints `web :80` (redirect to `websecure`) and `websecure :443`; file provider
    `/etc/traefik/dynamic.yml`; access log on; dashboard off.
  - `dynamic.yml`: router `api` = ``Host(`ephoros.localhost`) && PathPrefix(`/api/v1`)`` priority 100 →
    `http://api:8000`; router `web` = ``Host(`ephoros.localhost`)`` priority 1 → `http://web:8080`;
    both `tls: {}`; `tls.certificates` → `/certs/local.pem` + `/certs/local-key.pem`.
  - `init.sql`: `CREATE SCHEMA IF NOT EXISTS auth; CREATE SCHEMA IF NOT EXISTS core;`
  - Recipes: `certs` → `mkdir -p infra/traefik/certs && mkcert -install && mkcert -cert-file infra/traefik/certs/local.pem -key-file infra/traefik/certs/local-key.pem ephoros.localhost localhost 127.0.0.1`;
    `up` → `docker compose up -d --build --wait`; `down` → `docker compose down`; `logs` → `docker compose logs -f`;
    `e2e` → `just up && pnpm nx e2e web-e2e`.
- [ ] **Step 5: Run** — `just certs && just e2e` → 3 passed.
  Also: `docker compose exec postgres psql -U ephoros -c '\dn'` lists `auth` and `core`;
  `docker compose stop redis && curl -sk https://ephoros.localhost/api/v1/readyz` → 503 problem+json
  with `"redis": "fail: …"`; `docker compose start redis`.
- [ ] **Step 6: Commit** — `feat(infra): run web and api behind Traefik TLS with Postgres and Redis`

---

### Task 9: Git hooks — lefthook, commitlint, gitleaks

**Files:**
- Create: `lefthook.yml`, `commitlint.config.mjs`
- Modify: `package.json` (devDeps `@commitlint/cli@21.2.4`, `@commitlint/config-conventional@21.2.4`),
  `justfile` (`setup` gains `lefthook install`)

**Interfaces:**
- Produces: pre-commit (`ruff check --fix` + `ruff format` on staged `*.py`; `prettier --write` and
  `eslint --fix` on staged `*.{ts,html,css,json,md,yml}`; `gitleaks protect --staged --redact`,
  `stage_fixed: true`), commit-msg (`pnpm commitlint --edit {1}`).

- [ ] **Step 1: Write the config files** above.
- [ ] **Step 2: Verify the bad path** — `git commit --allow-empty -m "bad message"` → rejected by commitlint;
  stage a file containing `AKIAABCDEFGHIJKLMNOP` → rejected by gitleaks; unstage and delete it.
- [ ] **Step 3: Verify the good path** — commit the hook files with `chore: add lefthook, commitlint and gitleaks hooks` → succeeds.

---

### Task 10: CI pipeline + README quick start

**Files:**
- Create: `.github/workflows/ci.yml`, `README.md`

**Interfaces:**
- Consumes: every just recipe and Nx target above.
- Produces: jobs `checks`, `e2e`, `security`, `images` (main only).

- [ ] **Step 1: Write `ci.yml`.** Triggers: `pull_request`, `push` to `main`. Shared setup:
  `actions/checkout` (`fetch-depth: 0`), `jdx/mise-action` (installs pinned tools, caches),
  pnpm store cache, `astral-sh/setup-uv` cache disabled in favor of `uv sync --frozen --all-packages`
  with `UV_CACHE_DIR` cached, `pnpm install --frozen-lockfile`.
  - `checks`: `nrwl/nx-set-shas`; `pnpm nx affected -t lint typecheck test build`; `just check-contract`.
  - `e2e` (needs `checks`): `cp .env.example .env`; `mkcert` certs without `-install`
    (`ignoreHTTPSErrors` covers trust); `pnpm exec playwright install --with-deps chromium`; `just e2e`;
    upload `playwright-report/` and `test-results/` on failure; `docker compose logs` on failure.
  - `security`: `gitleaks/gitleaks-action`; `uv export --frozen --no-dev --all-packages -o req.txt && uvx pip-audit -r req.txt`;
    `pnpm audit --prod --audit-level high`; build both images and scan with `aquasecurity/trivy-action`
    (`severity: CRITICAL,HIGH`, `ignore-unfixed: true`, `exit-code: 1`).
  - `images` (push to `main`, needs all): `docker/login-action` to GHCR with `GITHUB_TOKEN`
    (`permissions: packages: write`), build+push `ghcr.io/${{ github.repository }}/{api,web}:${{ github.sha }}`.
  `concurrency` cancels superseded PR runs.
- [ ] **Step 2: Verify locally what can run locally** — `uvx zizmor .github/workflows/ci.yml`
  (workflow security lint) → no high findings; `just lint test` → green. Remote run happens on first push.
- [ ] **Step 3: Write `README.md`** — one paragraph on what Ephoros is (spec §1.1), prerequisites
  (mise, Docker), quick start (`mise install && just setup && cp .env.example .env && just certs && just up`
  → open `https://ephoros.localhost`), `just --list` for commands, links to the two specs.
- [ ] **Step 4: Commit** — `ci: add checks, e2e, security and image workflows; add README`

---

### Milestone close

- [ ] Fresh-clone check: `git clone . /tmp/eph-m1 && cd /tmp/eph-m1 && cp .env.example .env && just setup && just e2e` → green.
- [ ] superpowers:requesting-code-review on the whole branch (ponytail-review checklist).
- [ ] ponytail:ponytail-debt → list every `shortcut:` and confirm each has an owning milestone.
- [ ] superpowers:finishing-a-development-branch.
