#!/usr/bin/env bash
set -euo pipefail

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
export CONTAINER_ENGINE

if [[ "$ENGINE_NAME" == "podman" ]]; then
    export KIND_EXPERIMENTAL_PROVIDER=podman
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DESTROY_COMMAND="terraform -chdir=infra destroy -auto-approve"
APPLY_COMMAND="terraform -chdir=infra apply -auto-approve"
ROLLOUT_COMMAND="kubectl rollout status deployment/agentsvc -n agentsvc --timeout=120s"

if ! terraform -chdir=infra destroy -auto-approve; then
    echo "The initial destroy did not find active infrastructure or could not complete. Continuing." >&2
fi

SECONDS=0
terraform -chdir=infra apply -auto-approve
COLD_DEPLOY_SECONDS=$SECONDS

kubectl rollout status deployment/agentsvc -n agentsvc --timeout=120s

echo "Note: The kind node image and base images are already pulled."
echo "This value measures cluster creation, image loading, and rollout, not image download."

python3 - "$COLD_DEPLOY_SECONDS" "$IMAGE" "$CLUSTER" "$ENGINE_NAME" "$APPLY_COMMAND" <<'PY'
import json
import sys

cold_deploy_seconds, image, cluster, engine, apply_command = sys.argv[1:]
print(
    json.dumps(
        {
            "cold_deploy_seconds": int(cold_deploy_seconds),
            "image": image,
            "cluster": cluster,
            "engine": engine,
            "commands": [apply_command],
        },
        separators=(",", ":"),
    )
)
PY
