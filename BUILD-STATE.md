# Build state

Status: PAUSED. Codex ran out of quota before it wrote any application file.
The repository holds this checkpoint file and nothing else.

Date paused: 2026-07-29.

## Target

A LangGraph agent service in Python. FastAPI wraps one agent graph and an
MCP-style JSON-RPC endpoint. A Dockerfile containerises it. Terraform creates a
local kind cluster and deploys the service. A GitHub Actions workflow lints,
tests, builds the image, and runs a smoke deploy on kind.

The project must measure at least one real number end to end. Two numbers are
planned: cold deploy time from `terraform apply` to the first ready pod, and p50
request latency through the Kubernetes Service.

## Done

The local toolchain is installed and proven. Nothing else is done.

| Item | State | Evidence |
|------|-------|----------|
| Project directory + `git init` | Done | this repo, branch `main` |
| podman VM `kind-demo` | Running, rootful, 4 CPU, 6 GB, 40 GB disk | `podman info` reports `rootless=false` |
| podman default connection | Set to `kind-demo-root` | `podman system connection list` |
| kind 0.32.0 | Installed | `brew install kind` |
| terraform 1.15.8 | Installed | `brew install hashicorp/tap/terraform` |
| kubectl 1.36.3 | Installed | `brew install kubernetes-cli` |
| kind on podman works | Proven | probe cluster `kindprobe` created and deleted |
| kubectl reaches a kind cluster from macOS | Proven | `kubectl get nodes` listed the control plane node |
| `python:3.12-slim` base image | Pulled into podman | `podman pull` |

The macOS host has no Docker. Docker Desktop is uninstalled and
`/usr/local/bin/docker` is a dangling symlink. kind therefore runs on podman.
Every kind command needs this environment variable:

```
export KIND_EXPERIMENTAL_PROVIDER=podman
```

The original `podman-machine-default` VM is broken. Its disk image is missing.
It was left untouched. The new `kind-demo` VM replaces it for this project.

## Not done

No application code. No Dockerfile. No Terraform. No CI workflow. No tests.
No measured metric.

## Mid-flight

Nothing is half-written. Codex wrote zero files. Step 1 can restart clean.

## Failure detail

The first `codex exec` call hung. It printed `Reading additional input from
stdin...` and never started. Cause: `codex exec` reads extra prompt text from
stdin when stdin stays open. Fix: append `< /dev/null` to every `codex exec`
call. This is already applied to the briefs below.

The second call started correctly and planned the work. It then stopped with
`ERROR: Quota exceeded. Check your plan and billing details` after 26,265
tokens. This is a billing limit, not a capability failure.

## Resume plan

Run the three briefs in order from this directory. Each one is a single
`codex exec` call. Review the diff after each. Verify before moving on.

### Step 1 of 3 — Python application

```
cd output/clusters/langgraph-k8s-deploy
timeout 600 codex exec --sandbox workspace-write "You are writing a small, honest, PUBLIC demo repo from scratch in the CURRENT directory (empty except .git and BUILD-STATE.md). Target: a LangGraph agent service that later gets containerised and deployed to a local kind Kubernetes cluster via Terraform.

THIS TASK = STEP 1 OF 3: the Python application only. Do NOT write Dockerfile, Terraform, or CI yet. Do NOT touch BUILD-STATE.md.

Constraints:
- Python 3.12. Use uv (pyproject.toml with a [project] table, no poetry).
- MUST run with ZERO API keys and ZERO network access at runtime. No OpenAI/Anthropic/Gemini clients. The 'model' is a deterministic local planner so the demo is reproducible and CI-safe.
- Keep it SMALL. One agent graph, a handful of files.

Create exactly this layout:

pyproject.toml
  [project] name='langgraph-k8s-deploy', version='0.1.0', requires-python='>=3.12,<3.13'
  dependencies: langgraph, fastapi, uvicorn[standard], pydantic
  [dependency-groups] dev: pytest, httpx, ruff
  [tool.ruff] line-length 100, lint select E,F,I,UP,B
  [tool.pytest.ini_options] testpaths=['tests']
  build backend hatchling, packages = ['src/agentsvc']

src/agentsvc/__init__.py
src/agentsvc/logging_config.py
  - configure_logging(level: str): stdlib logging with a JSON formatter writing single-line JSON to stdout with keys ts (ISO8601 UTC), level, logger, msg, plus any extra fields passed through the logging 'extra' dict. No third-party log libraries.

src/agentsvc/tools.py
  - Two pure offline tools with JSON-Schema descriptions:
    1) 'word_count' -> {text: str} -> {'words': int, 'chars': int}
    2) 'unit_convert' -> {value: float, from_unit: str, to_unit: str} supporting c<->f and km<->mi -> {'value': float, 'unit': str}
  - A TOOLS registry: dict name -> object with .name, .description, .input_schema (JSON Schema dict), .call(args: dict) -> dict
  - call_tool(name, args) raises a custom ToolError on unknown tool or bad arguments.

src/agentsvc/graph.py
  - A LangGraph StateGraph with a TypedDict state: question str, plan str, tool_name str|None, tool_args dict|None, tool_result dict|None, answer str, steps list[str]
  - Nodes: 'plan' (deterministic rule-based router that picks a tool from the question text, or none), 'act' (calls call_tool and records tool_result), 'respond' (formats a final natural-language answer from state).
  - Conditional edge from 'plan': go to 'act' when tool_name is set, else go to 'respond'. 'act' -> 'respond' -> END.
  - Export build_graph() returning a compiled graph, and a module-level lazily built singleton accessor get_graph().
  - Every node appends a short string to state['steps'] so the API can show the trace.

src/agentsvc/api.py
  - FastAPI app created by a create_app() factory. Include:
    - GET /healthz -> {'status':'ok'} always 200 (liveness)
    - GET /readyz -> 200 {'status':'ready'} only when the graph compiled, else 503 (readiness). Compile the graph in a FastAPI lifespan startup handler.
    - POST /invoke body {question: str} -> {answer, steps, tool_name, tool_result, latency_ms}
    - MCP-style JSON-RPC 2.0 endpoint POST /mcp accepting methods 'tools/list' and 'tools/call'. Follow the JSON-RPC 2.0 envelope exactly: request {jsonrpc:'2.0', id, method, params}; success {jsonrpc:'2.0', id, result}; error {jsonrpc:'2.0', id, error:{code,message}} with -32601 for an unknown method and -32602 for invalid params. tools/list returns {'tools':[{name, description, inputSchema}]}. tools/call takes params {name, arguments} and returns {'content':[{'type':'text','text': <json dumped result>}], 'isError': false}.
    - Middleware that assigns a request_id (uuid4 hex), times the request, and emits one structured JSON log line per request with fields request_id, method, path, status, duration_ms.
  - Read LOG_LEVEL and APP_VERSION from environment variables with sane defaults.

src/agentsvc/__main__.py
  - uvicorn entrypoint honouring HOST (default 0.0.0.0) and PORT (default 8000).

tests/test_tools.py, tests/test_graph.py, tests/test_api.py
  - pytest plus fastapi TestClient. Cover both tools happy path and error, graph routing with and without a tool, /healthz, /readyz, /invoke, and all four /mcp cases (tools/list, tools/call success, unknown method -32601, bad params -32602).

.gitignore  (python, .venv, __pycache__, .pytest_cache, .ruff_cache, *.pyc, .terraform*, terraform.tfstate*, .DS_Store)
LICENSE (MIT, copyright line: 'Copyright (c) 2026 langgraph-k8s-deploy contributors')

Do NOT create a README, I write that. Do NOT mention any employer, person, or company anywhere in the code. Write the files correctly; I run the verification myself. If you can run 'uv sync' and 'uv run pytest' then do, otherwise just finish." < /dev/null
```

Verify step 1 with `uv sync`, `uv run ruff check .`, and `uv run pytest -q`.

### Step 2 of 3 — Dockerfile and Terraform

```
timeout 600 codex exec --sandbox workspace-write "STEP 2 OF 3 in this repo. The Python app under src/agentsvc already exists and its tests pass. Do NOT change application code. Do NOT touch BUILD-STATE.md. Add containerisation and Terraform only.

Host context you must respect: macOS with NO Docker. The container engine is podman and kind runs with KIND_EXPERIMENTAL_PROVIDER=podman. CI on GitHub Actions uses Docker. Every script you write must work with either engine by resolving a CONTAINER_ENGINE variable: use \$CONTAINER_ENGINE if set, else 'docker' if on PATH, else 'podman'.

Create:

Dockerfile
  - Multi-stage. Stage 1 uses ghcr.io/astral-sh/uv:python3.12-bookworm-slim to install dependencies into /app/.venv with 'uv sync --frozen --no-dev'. Stage 2 uses python:3.12-slim, copies /app/.venv and src, runs as a non-root user (uid 10001), sets PATH to the venv, EXPOSE 8000, CMD ['python','-m','agentsvc'].
  - Add a .dockerignore covering .git, .venv, tests, __pycache__, infra, .github, *.md.

scripts/load-image.sh
  - Resolve CONTAINER_ENGINE as described. Build the image with tag \$IMAGE (default 'langgraph-agentsvc:dev'). Load it into the kind cluster named \$CLUSTER (default 'langgraph-demo'). For docker use 'kind load docker-image'. For podman, 'podman save' to a temporary tar then 'kind load image-archive'. set -euo pipefail. Export KIND_EXPERIMENTAL_PROVIDER=podman when the engine is podman.

infra/versions.tf
  - terraform required_version '>= 1.6.0'. required_providers: kind from 'tehcyx/kind' version '~> 0.9', kubernetes from 'hashicorp/kubernetes' version '~> 2.35'.

infra/variables.tf
  - cluster_name default 'langgraph-demo', namespace default 'agentsvc', image default 'langgraph-agentsvc:dev', replicas default 2, node_port default 30080, app_version default '0.1.0', log_level default 'INFO'.

infra/main.tf
  - resource kind_cluster with wait_for_ready = true and a kind_config block: one control-plane node with extra_port_mappings container_port = var.node_port, host_port = var.node_port, listen_address '0.0.0.0'.
  - provider kubernetes configured from the kind_cluster attributes: host = endpoint, cluster_ca_certificate, client_certificate, client_key.
  - a terraform_data resource that depends on the cluster and runs scripts/load-image.sh through local-exec, passing IMAGE and CLUSTER as environment variables, triggered by var.image.
  - kubernetes_namespace, kubernetes_config_map (LOG_LEVEL, APP_VERSION), kubernetes_deployment_v1 with var.replicas replicas, image_pull_policy 'IfNotPresent', container port 8000, env_from the config map, resources requests cpu 50m memory 128Mi and limits cpu 500m memory 512Mi, liveness_probe on GET /healthz and readiness_probe on GET /readyz, and wait_for_rollout = true. The deployment must depend on the image load.
  - kubernetes_service_v1 of type NodePort mapping port 80 to target 8000 on node_port var.node_port.

infra/outputs.tf
  - service_url = 'http://localhost:\${var.node_port}', cluster_name, namespace, kubeconfig path.

Keep it to those files. No Helm. No cloud providers. No secrets, no credentials, no hardcoded tokens. Do NOT run terraform, I run it. Do NOT mention any employer, person, or company." < /dev/null
```

Verify step 2 with `terraform -chdir=infra init` then `terraform -chdir=infra validate` and `terraform -chdir=infra fmt -check`.

### Step 3 of 3 — CI workflow, smoke test, measurement scripts

```
timeout 600 codex exec --sandbox workspace-write "STEP 3 OF 3 in this repo. The app, Dockerfile, and infra/ Terraform already exist. Do NOT change them. Do NOT touch BUILD-STATE.md or README.md. Add CI and measurement only.

Create:

scripts/smoke.sh
  - set -euo pipefail. Takes a base URL, default http://localhost:30080. Polls GET /healthz and GET /readyz until both return 200 or a 120 second deadline passes. Then asserts POST /invoke with {\"question\":\"how many words are in this sentence\"} returns HTTP 200 and a non-empty 'answer'. Then asserts POST /mcp with a JSON-RPC tools/list request returns a 'result.tools' array with 2 entries. Exit non-zero with a clear message on any failure. Use curl and python3 for JSON assertions, no jq dependency.

scripts/bench.py
  - Standard library only. Arguments: --url (default http://localhost:30080/invoke), --requests (default 200), --warmup (default 20), --concurrency (default 1). POSTs {\"question\":\"convert 100 km to mi\"} and records wall-clock latency per request. Prints a single JSON object with count, p50_ms, p95_ms, p99_ms, min_ms, max_ms, errors. Round to 2 decimals.

scripts/measure-deploy.sh
  - set -euo pipefail. Measures cold deploy time. Destroys any existing stack, then times 'terraform -chdir=infra apply -auto-approve' from start until the deployment is rolled out. Records the seconds with the shell SECONDS builtin. Then runs 'kubectl rollout status' as a confirmation. Prints a JSON object with cold_deploy_seconds and the exact commands it ran. It must export KIND_EXPERIMENTAL_PROVIDER=podman when podman is the engine.

scripts/ci-local.sh
  - set -euo pipefail. Runs the same ordered steps as the GitHub Actions workflow on the local machine: uv sync, ruff check, ruff format --check, pytest, container image build, terraform init/validate, terraform apply, smoke.sh, bench.py, terraform destroy. Print a clear banner before each step and a PASS/FAIL summary at the end.

.github/workflows/ci.yml
  - Two jobs on ubuntu-latest, triggered on push and pull_request to main.
  - Job 'lint-test': checkout, astral-sh/setup-uv@v5, 'uv sync --frozen', 'uv run ruff check .', 'uv run ruff format --check .', 'uv run pytest -q'.
  - Job 'deploy-smoke' needs lint-test: checkout, setup-uv, hashicorp/setup-terraform@v3, helm/kind-action@v1 is NOT used because Terraform creates the cluster. Build the image with docker build, then 'terraform -chdir=infra init' and 'terraform -chdir=infra apply -auto-approve', then run scripts/smoke.sh, then run scripts/bench.py and print the JSON, then always 'terraform -chdir=infra destroy -auto-approve' in an if: always() step.
  - Pin every action to a major version tag. No secrets. No registry push.

Do NOT run anything that needs a cluster, I run those. Do NOT mention any employer, person, or company." < /dev/null
```

Verify step 3 by running `bash scripts/ci-local.sh` on this machine.

### After step 3

1. Measure the two numbers with `scripts/measure-deploy.sh` and `scripts/bench.py`.
2. Write `README.md` by hand. Open with a 3-line summary of what the repo shows.
   Record both measured numbers and the exact command that produced each.
3. Record the proof points in `article-digest.md` and `data/gap-projects.md` in
   career-ops, per rule P6.5.
4. Publish only after review. See the publication commands at the end.

## Environment recipe for any new session

```
export PATH=/usr/local/bin:$PATH
export KIND_EXPERIMENTAL_PROVIDER=podman
podman machine start kind-demo          # if the VM is stopped
podman system connection default kind-demo-root
podman info --format '{{.Host.Security.Rootless}}'   # expect false
```

## Publication, after review only

Not done yet. Do not run these until the build is complete and Sun approves.

```
gh repo create Bl4ckd09/langgraph-k8s-deploy --public --source . --remote origin --push
gh api -X PUT repos/Bl4ckd09/langgraph-k8s-deploy/pin   # or pin from the profile page
```

## Rules that govern this build

- Codex writes all code. The main agent specs, reviews, and runs.
- No employer code, no employer data, no personal claims in this repo.
- Never record a metric that was not measured.
- Commit messages carry no AI attribution trailer.
