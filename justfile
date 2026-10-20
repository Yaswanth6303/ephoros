# Ephoros command entrypoint. Each recipe delegates to one tool; no logic here.

default:
    @just --list

# install pinned tools and all dependencies
setup:
    mise install
