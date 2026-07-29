#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-langgraph-agentsvc:dev}"
CLUSTER="${CLUSTER:-langgraph-demo}"

if [[ -z "${CONTAINER_ENGINE:-}" ]]; then
    if command -v docker >/dev/null 2>&1; then
        CONTAINER_ENGINE="docker"
    elif command -v podman >/dev/null 2>&1; then
        CONTAINER_ENGINE="podman"
    else
        echo "No container engine found. Set CONTAINER_ENGINE to docker or podman." >&2
        exit 1
    fi
fi

if ! command -v "$CONTAINER_ENGINE" >/dev/null 2>&1; then
    echo "Container engine not found: $CONTAINER_ENGINE" >&2
    exit 1
fi

ENGINE_NAME="$(basename "$CONTAINER_ENGINE")"
if [[ "$ENGINE_NAME" != "docker" && "$ENGINE_NAME" != "podman" ]]; then
    echo "Unsupported container engine: $CONTAINER_ENGINE" >&2
    exit 1
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

run() {
    printf "+"
    printf " %q" "$@"
    printf "\n"
    "$@"
}

run cd "$REPO_ROOT"
run "$CONTAINER_ENGINE" build --tag "$IMAGE" .

if [[ "$ENGINE_NAME" == "docker" ]]; then
    run kind load docker-image "$IMAGE" --name "$CLUSTER"
else
    echo "+ export KIND_EXPERIMENTAL_PROVIDER=podman"
    export KIND_EXPERIMENTAL_PROVIDER=podman

    IMAGE_TAR="$(mktemp -t langgraph-agentsvc-image)"
    cleanup() {
        run rm -f "$IMAGE_TAR"
    }
    trap cleanup EXIT

    run "$CONTAINER_ENGINE" save --output "$IMAGE_TAR" "$IMAGE"
    run kind load image-archive "$IMAGE_TAR" --name "$CLUSTER"
fi
