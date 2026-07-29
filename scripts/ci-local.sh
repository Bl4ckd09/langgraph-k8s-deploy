#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-docker.io/library/langgraph-agentsvc:dev}"

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

STEP_NAMES=()
STEP_RESULTS=()
OVERALL_STATUS=0

banner() {
    printf "\n========== %s ==========\n" "$1"
}

record_result() {
    STEP_NAMES+=("$1")
    STEP_RESULTS+=("$2")
}

run_step() {
    local name="$1"
    shift
    banner "$name"
    if "$@"; then
        record_result "$name" "PASS"
        return 0
    fi
    record_result "$name" "FAIL"
    OVERALL_STATUS=1
    return 1
}

print_summary() {
    local index
    printf "\n%-42s %s\n" "STEP" "RESULT"
    printf "%-42s %s\n" "------------------------------------------" "------"
    for ((index = 0; index < ${#STEP_NAMES[@]}; index++)); do
        printf "%-42s %s\n" "${STEP_NAMES[$index]}" "${STEP_RESULTS[$index]}"
    done
}

cleanup() {
    local incoming_status=$?
    trap - EXIT
    set +e
    banner "terraform destroy"
    if terraform -chdir=infra destroy -auto-approve; then
        record_result "terraform destroy" "PASS"
    else
        record_result "terraform destroy" "FAIL"
        OVERALL_STATUS=1
    fi
    print_summary
    if ((incoming_status != 0 || OVERALL_STATUS != 0)); then
        exit 1
    fi
    exit 0
}
trap cleanup EXIT

run_step "uv sync --frozen" uv sync --frozen || exit 1
run_step "ruff check" uv run ruff check . || exit 1
run_step "ruff format check" uv run ruff format --check . || exit 1
run_step "pytest" uv run pytest -q || exit 1
run_step "container image build" "$CONTAINER_ENGINE" build --tag "$IMAGE" . || exit 1
run_step "terraform init" terraform -chdir=infra init || exit 1
run_step "terraform validate" terraform -chdir=infra validate || exit 1
run_step "terraform apply" terraform -chdir=infra apply -auto-approve || exit 1
run_step "smoke test" scripts/smoke.sh || exit 1
run_step "latency benchmark" python3 scripts/bench.py || exit 1
