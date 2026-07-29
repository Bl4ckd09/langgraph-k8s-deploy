from typing import Any

from agentsvc.graph import build_graph


def _state(question: str) -> dict[str, Any]:
    return {
        "question": question,
        "plan": "",
        "tool_name": None,
        "tool_args": None,
        "tool_result": None,
        "answer": "",
        "steps": [],
    }


def test_graph_routes_through_a_tool() -> None:
    result = build_graph().invoke(_state("Convert 10 km to mi"))

    assert result["tool_name"] == "unit_convert"
    assert result["tool_result"]["unit"] == "mi"
    assert result["steps"] == ["plan: unit_convert", "act: unit_convert", "respond"]


def test_graph_routes_directly_to_response_without_a_tool() -> None:
    result = build_graph().invoke(_state("What can you do?"))

    assert result["tool_name"] is None
    assert result["tool_result"] is None
    assert result["steps"] == ["plan: no tool", "respond"]

