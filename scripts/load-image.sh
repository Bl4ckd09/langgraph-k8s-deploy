#!/usr/bin/env bash
set -euo pipefail

# Keep this reference fully qualified. Podman prefixes unqualified tags with
# localhost/, while containerd normalizes them to docker.io/library/. They must
# agree so imagePullPolicy IfNotPresent can find the preloaded image.
IMAGE="${IMAGE:-docker.io/library/langgraph-agentsvc:dev}"
CLUSTER="${CLUSTER:-langgraph-demo}"

engine_works() {
    "$1" info >/dev/null 2>&1
}

if [[ -z "${CONTAINER_ENGINE:-}" ]]; then
    if engine_works docker; then
        CONTAINER_ENGINE="docker"
    elif engine_works podman; then
        CONTAINER_ENGINE="podman"
    else
        echo "No working container engine found. Set CONTAINER_ENGINE to docker or podman." >&2
        exit 1
    fi
elif ! engine_works "$CONTAINER_ENGINE"; then
    echo "Container engine cannot run: $CONTAINER_ENGINE" >&2
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

printf "+ kind get nodes --name %q\n" "$CLUSTER"
NODES="$(kind get nodes --name "$CLUSTER")"
printf "%s\n" "$NODES"

CONTROL_PLANE_NODE=""
while IFS= read -r node; do
    if [[ "$node" == *control-plane* ]]; then
        CONTROL_PLANE_NODE="$node"
        break
    fi
done <<<"$NODES"

if [[ -z "$CONTROL_PLANE_NODE" ]]; then
    echo "Image verification failed: no control-plane node found in cluster $CLUSTER." >&2
    exit 1
fi

printf "+ %q exec %q crictl images\n" "$CONTAINER_ENGINE" "$CONTROL_PLANE_NODE"
NODE_IMAGES="$("$CONTAINER_ENGINE" exec "$CONTROL_PLANE_NODE" crictl images)"
printf "%s\n" "$NODE_IMAGES"

IMAGE_REPOSITORY="${IMAGE%:*}"
if ! grep -Fq -- "$IMAGE_REPOSITORY" <<<"$NODE_IMAGES"; then
    echo "Image verification failed: repository $IMAGE_REPOSITORY is missing from node $CONTROL_PLANE_NODE." >&2
    exit 1
fi
