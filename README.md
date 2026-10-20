# Ephoros

Ephemeral Cloud & Kubernetes Resource Risk Detection. Cloud-native environments constantly create
and destroy short-lived resources — CI/CD pods, spot VMs, temporary IAM sessions — that daily
inventory scans miss. Ephoros discovers these transient assets in near real time, detects risky
behaviour, correlates detections into incidents, scores them and explains them for analysts.

Built for the iamneo × Société Générale challenge
[_Ephemeral Cloud & Kubernetes Resource Risk Detection_](https://societegenerale.iamneo.ai/ephemeral-cloud-kubernetes-resource-risk-detection/).

## Quick start

Prerequisites: [mise](https://mise.jdx.dev) and Docker.

```sh
mise install            # pinned node, pnpm, python, uv, just, mkcert, …
just setup              # pnpm + uv dependencies, git hooks
cp .env.example .env
just certs              # trusted local TLS cert (asks for your password once)
just up                 # Traefik, web, api, Postgres, Redis
```

Open <https://ephoros.localhost>. Run `just` to list every command (`just dev`, `just test`,
`just e2e`, `just gen-client`, …).

## Docs

- [Design spec](docs/superpowers/specs/2026-10-10-ephoros-design.md)
- [AI layer design](docs/superpowers/specs/2026-10-10-ephoros-ai-layer-design.md)
- [Milestone plans](docs/superpowers/plans/)
