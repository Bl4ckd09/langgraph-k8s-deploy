"""A deterministic LangGraph workflow for the offline agent."""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .tools import call_tool


class AgentState(TypedDict):
    question: str
    plan: str
    tool_name: str | None
    tool_args: dict[str, Any] | None
    tool_result: dict[str, Any] | None
    answer: str
    steps: list[str]


_CONVERSION_PATTERN = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(c|f|km|mi)\s+(?:to|in)\s+(c|f|km|mi)\b",
    re.IGNORECASE,
)


def _word_count_text(question: str) -> str:
    quoted = re.search(r'["\'](.+?)["\']', question)
    if quoted:
        return quoted.group(1)
    if ":" in question:
        return question.split(":", maxsplit=1)[1].strip()
    return re.sub(
        r"^(?:please\s+)?(?:count\s+(?:the\s+)?words?\s+(?:in\s+)?|word\s+count\s+)",
        "",
        question,
        flags=re.IGNORECASE,
    ).strip()


def _plan(state: AgentState) -> dict[str, Any]:
    question = state["question"].strip()
    lowered = question.lower()
    steps = list(state.get("steps", []))

    if "word count" in lowered or re.search(r"\bcount (?:the )?words?\b", lowered):
        return {
            "plan": "Use word_count for the supplied text.",
            "tool_name": "word_count",
            "tool_args": {"text": _word_count_text(question)},
            "tool_result": None,
            "answer": "",
            "steps": [*steps, "plan: word_count"],
        }

    conversion = _CONVERSION_PATTERN.search(question)
    if conversion:
        value, from_unit, to_unit = conversion.groups()
        return {
            "plan": "Use unit_convert for the requested conversion.",
            "tool_name": "unit_convert",
            "tool_args": {
                "value": float(value),
                "from_unit": from_unit.lower(),
                "to_unit": to_unit.lower(),
            },
            "tool_result": None,
            "answer": "",
            "steps": [*steps, "plan: unit_convert"],
        }

    return {
        "plan": "Respond without a tool.",
        "tool_name": None,
        "tool_args": None,
        "tool_result": None,
        "answer": "",
        "steps": [*steps, "plan: no tool"],
    }


def _act(state: AgentState) -> dict[str, Any]:
    tool_name = state["tool_name"]
    tool_args = state["tool_args"]
    if tool_name is None or tool_args is None:
        raise ValueError("The act node requires a planned tool")
    return {
        "tool_result": call_tool(tool_name, tool_args),
        "steps": [*state["steps"], f"act: {tool_name}"],
    }


def _respond(state: AgentState) -> dict[str, Any]:
    result = state.get("tool_result")
    if state.get("tool_name") == "word_count" and result is not None:
        answer = f"The text has {result['words']} words and {result['chars']} characters."
    elif state.get("tool_name") == "unit_convert" and result is not None:
        answer = f"The converted value is {result['value']:.6g} {result['unit']}."
    else:
        answer = "I can count words or convert c and f temperatures or km and mi distances."
    return {"answer": answer, "steps": [*state["steps"], "respond"]}


def _route_after_plan(state: AgentState) -> str:
    return "act" if state.get("tool_name") else "respond"


def build_graph() -> Any:
    """Build and compile the agent graph."""
    builder = StateGraph(AgentState)
    builder.add_node("plan", _plan)
    builder.add_node("act", _act)
    builder.add_node("respond", _respond)
    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", _route_after_plan, {"act": "act", "respond": "respond"})
    builder.add_edge("act", "respond")
    builder.add_edge("respond", END)
    return builder.compile()


_GRAPH: Any | None = None


def get_graph() -> Any:
    """Return the process-wide graph instance and build it on first use."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH
