import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from agentsvc.api import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_invoke(client: TestClient) -> None:
    response = client.post("/invoke", json={"question": "Count words: one two three"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer"] == "The text has 3 words and 13 characters."
    assert body["steps"] == ["plan: word_count", "act: word_count", "respond"]
    assert body["tool_name"] == "word_count"
    assert body["tool_result"] == {"words": 3, "chars": 13}
    assert body["latency_ms"] >= 0


def test_invoke_rejects_oversized_question(client: TestClient) -> None:
    response = client.post("/invoke", json={"question": "x" * 4_097})
    assert response.status_code == 422


def test_rejects_oversized_request_body(client: TestClient) -> None:
    response = client.post(
        "/invoke",
        content=b"x" * 16_385,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_mcp_tools_list(client: TestClient) -> None:
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert [tool["name"] for tool in body["result"]["tools"]] == [
        "word_count",
        "unit_convert",
    ]
    assert "inputSchema" in body["result"]["tools"][0]


def test_mcp_tools_call(client: TestClient) -> None:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {"name": "word_count", "arguments": {"text": "two words"}},
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "call-1"
    assert body["result"]["isError"] is False
    assert json.loads(body["result"]["content"][0]["text"]) == {"words": 2, "chars": 9}


def test_mcp_unknown_method(client: TestClient) -> None:
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "missing", "params": {}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "jsonrpc": "2.0",
        "id": 2,
        "error": {"code": -32601, "message": "Method not found"},
    }


def test_mcp_bad_params(client: TestClient) -> None:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "word_count"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "jsonrpc": "2.0",
        "id": 3,
        "error": {"code": -32602, "message": "Invalid params"},
    }
