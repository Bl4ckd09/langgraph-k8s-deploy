#!/usr/bin/env python3
"""Run a small HTTP latency benchmark against the invoke endpoint."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import statistics
import time
import urllib.error
import urllib.request

REQUEST_BODY = json.dumps({"question": "convert 100 km to mi"}).encode()


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be at least 0")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:30080/invoke")
    parser.add_argument("--requests", type=positive_int, default=200)
    parser.add_argument("--warmup", type=non_negative_int, default=20)
    parser.add_argument("--concurrency", type=positive_int, default=1)
    return parser.parse_args()


def timed_request(url: str) -> tuple[float, bool]:
    request = urllib.request.Request(
        url,
        data=REQUEST_BODY,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            succeeded = response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        succeeded = False
    elapsed_ms = (time.perf_counter() - started) * 1000
    return elapsed_ms, succeeded


def run_requests(url: str, count: int, concurrency: int) -> list[tuple[float, bool]]:
    if concurrency == 1:
        return [timed_request(url) for _ in range(count)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        return list(executor.map(lambda _: timed_request(url), range(count)))


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    # Nearest-rank uses the value at ceil(percentile * count), with ranks starting at one.
    rank = math.ceil(percentile * len(values))
    return values[rank - 1]


def main() -> int:
    args = parse_args()

    run_requests(args.url, args.warmup, args.concurrency)
    results = run_requests(args.url, args.requests, args.concurrency)

    latencies = sorted(latency for latency, _ in results)
    errors = sum(not succeeded for _, succeeded in results)
    output = {
        "url": args.url,
        "count": args.requests,
        "concurrency": args.concurrency,
        "p50_ms": round(percentile_nearest_rank(latencies, 0.50), 2),
        "p95_ms": round(percentile_nearest_rank(latencies, 0.95), 2),
        "p99_ms": round(percentile_nearest_rank(latencies, 0.99), 2),
        "min_ms": round(latencies[0], 2),
        "max_ms": round(latencies[-1], 2),
        "mean_ms": round(statistics.fmean(latencies), 2),
        "errors": errors,
    }
    print(json.dumps(output, separators=(",", ":")))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
