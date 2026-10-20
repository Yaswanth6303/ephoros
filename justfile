# Ephoros command entrypoint. Each recipe delegates to one tool; no logic here.
set dotenv-load := false

default:
    @just --list

# install pinned tools and all dependencies
setup:
    mise install
