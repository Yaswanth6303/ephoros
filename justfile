# Ephoros command entrypoint. Each recipe delegates to one tool; no logic here.

default:
    @just --list

# install pinned tools and all dependencies
setup:
    mise install
    pnpm install
    uv sync --all-packages

# run the dev stack: infra in Docker, web + api with hot reload
dev:
    docker compose up -d postgres redis && pnpm nx run-many -t serve -p web api

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
