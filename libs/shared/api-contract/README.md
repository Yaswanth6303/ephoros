# api-contract

TypeScript client for the Ephoros API, generated from FastAPI's OpenAPI document by
[hey-api](https://heyapi.dev). Do not edit `openapi.json` or `src/generated/` by hand:
run `just gen-client`. CI fails if they drift from the API (`just check-contract`).
