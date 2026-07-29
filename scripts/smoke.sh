#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:30080}"
BASE_URL="${BASE_URL%/}"

fail() {
    printf "SMOKE FAIL: %s\n" "$*" >&2
    exit 1
}

http_status() {
    local status
    status="$(
        curl --silent \
            --output /dev/null \
            --write-out "%{http_code}" \
            --connect-timeout 2 \
            --max-time 5 \
            "$1" 2>/dev/null
    )" || status="000"
    printf "%s" "$status"
}

START_SECONDS=$SECONDS
NEXT_PROGRESS_SECONDS=10

while true; do
    HEALTH_STATUS="$(http_status "$BASE_URL/healthz")"
    READY_STATUS="$(http_status "$BASE_URL/readyz")"

    if [[ "$HEALTH_STATUS" == "200" && "$READY_STATUS" == "200" ]]; then
        break
    fi

    ELAPSED_SECONDS=$((SECONDS - START_SECONDS))
    if ((ELAPSED_SECONDS >= 120)); then
        fail "GET /healthz and GET /readyz did not both return HTTP 200 within 120 seconds (healthz=$HEALTH_STATUS, readyz=$READY_STATUS)"
    fi

    if ((ELAPSED_SECONDS >= NEXT_PROGRESS_SECONDS)); then
        printf "Waiting for health checks: %ss elapsed (healthz=%s, readyz=%s)\n" \
            "$ELAPSED_SECONDS" "$HEALTH_STATUS" "$READY_STATUS"
        NEXT_PROGRESS_SECONDS=$((NEXT_PROGRESS_SECONDS + 10))
    fi

    sleep 1
done

RESPONSE_FILE="$(mktemp "${TMPDIR:-/tmp}/agentsvc-smoke.XXXXXX")"
cleanup() {
    rm -f "$RESPONSE_FILE"
}
trap cleanup EXIT

if ! HTTP_STATUS="$(
    curl --silent \
        --show-error \
        --output "$RESPONSE_FILE" \
        --write-out "%{http_code}" \
        --max-time 30 \
        --header "Content-Type: application/json" \
        --data '{"question":"how many words are in this sentence"}' \
        "$BASE_URL/invoke"
)"; then
    fail "POST /invoke request did not complete"
fi
[[ "$HTTP_STATUS" == "200" ]] || fail "POST /invoke returned HTTP $HTTP_STATUS instead of 200"
if ! python3 - "$RESPONSE_FILE" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as response_file:
        body = json.load(response_file)
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)

answer = body.get("answer") if isinstance(body, dict) else None
if not isinstance(answer, str) or not answer.strip():
    raise SystemExit(1)
PY
then
    fail "POST /invoke response did not contain a non-empty answer field"
fi

if ! HTTP_STATUS="$(
    curl --silent \
        --show-error \
        --output "$RESPONSE_FILE" \
        --write-out "%{http_code}" \
        --max-time 30 \
        --header "Content-Type: application/json" \
        --data '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
        "$BASE_URL/mcp"
)"; then
    fail "POST /mcp tools/list request did not complete"
fi
[[ "$HTTP_STATUS" == "200" ]] || fail "POST /mcp tools/list returned HTTP $HTTP_STATUS instead of 200"
if ! python3 - "$RESPONSE_FILE" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as response_file:
        body = json.load(response_file)
    tools = body["result"]["tools"]
except (OSError, json.JSONDecodeError, KeyError, TypeError):
    raise SystemExit(1)

if not isinstance(tools, list) or len(tools) != 2:
    raise SystemExit(1)
PY
then
    fail "POST /mcp tools/list response did not contain result.tools as an array of exactly 2 entries"
fi

if ! HTTP_STATUS="$(
    curl --silent \
        --show-error \
        --output "$RESPONSE_FILE" \
        --write-out "%{http_code}" \
        --max-time 30 \
        --header "Content-Type: application/json" \
        --data '{"jsonrpc":"2.0","id":2,"method":"unknown","params":{}}' \
        "$BASE_URL/mcp"
)"; then
    fail "POST /mcp unknown-method request did not complete"
fi
[[ "$HTTP_STATUS" == "200" ]] || fail "POST /mcp unknown-method returned HTTP $HTTP_STATUS instead of 200"
if ! python3 - "$RESPONSE_FILE" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as response_file:
        body = json.load(response_file)
    error_code = body["error"]["code"]
except (OSError, json.JSONDecodeError, KeyError, TypeError):
    raise SystemExit(1)

if error_code != -32601:
    raise SystemExit(1)
PY
then
    fail "POST /mcp unknown-method response did not contain error.code -32601"
fi

printf "SMOKE PASS: all endpoint assertions passed\n"
