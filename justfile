# Ephoros command entrypoint. Each recipe delegates to one tool; no logic here.

# recipes see .env even where mise loaded the environment before .env existed (CI)
set dotenv-load

default:
    @just --list

# install pinned tools and all dependencies
setup:
    mise install
    pnpm install
    uv sync --all-packages
    lefthook install

# run the dev stack: infra in Docker, web + api with hot reload
dev:
    docker compose up -d postgres redis && pnpm nx run-many -t serve serve-worker -p web api auth

test:
    pnpm nx run-many -t test

lint:
    pnpm nx run-many -t lint

typecheck:
    pnpm nx run-many -t typecheck

fmt:
    uv run ruff format . && pnpm nx format:write

# regenerate the TypeScript API client from FastAPI's OpenAPI document
gen-client:
    pnpm nx run api-contract:generate --skip-nx-cache

# fail if the committed client differs from what the API generates (CI)
check-contract: gen-client
    git diff --exit-code HEAD -- libs/shared/api-contract
    test -z "$(git ls-files --others --exclude-standard libs/shared/api-contract)"

# create a locally trusted TLS certificate for https://ephoros.localhost
certs:
    mkdir -p infra/traefik/certs && mkcert -install && mkcert -cert-file infra/traefik/certs/local.pem -key-file infra/traefik/certs/local-key.pem ephoros.localhost localhost 127.0.0.1

# build and start the full stack, waiting until healthy
up:
    docker compose up -d --build --wait

down:
    docker compose down

logs:
    docker compose logs -f

# full stack + Playwright smoke tests
e2e: up migrate seed
    pnpm nx e2e web-e2e

# apply database migrations: core (Alembic) and auth (Drizzle)
migrate:
    uv run alembic -c apps/api/alembic.ini upgrade head && pnpm nx run auth:db-migrate

# create the dev admin and analyst users from SEED_* env vars (idempotent)
seed:
    pnpm nx run auth:seed

# generate a labelled dataset starting now and replay it onto events.raw (speed 0 = as fast as
# possible, 1 = real time). Each run is a new dataset; for a reproducible one pass a fixed start:
# uv run ephoros-sim generate --seed 7 --start 2026-01-05T08:00:00Z --replay
simulate seed="7" speed="0":
    uv run --package ephoros-simulator ephoros-sim generate --seed {{seed}} --replay --speed {{speed}}
