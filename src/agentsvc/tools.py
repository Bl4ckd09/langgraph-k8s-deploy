"""Deterministic tools that do not use network services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ToolError(ValueError):
    """Raised when a tool name or its arguments are invalid."""


@dataclass(frozen=True)
class OfflineTool:
    """A small tool definition with a JSON Schema interface."""

    name: str
    description: str
    input_schema: dict[str, Any]
    _function: Callable[[dict[str, Any]], dict[str, Any]]

    def call(self, args: dict[str, Any]) -> dict[str, Any]:
        """Call the tool with validated arguments."""
        return self._function(args)


def _require_exact_keys(args: dict[str, Any], expected: set[str]) -> None:
    if not isinstance(args, dict):
        raise ToolError("Tool arguments must be an object")
    if set(args) != expected:
        raise ToolError(f"Tool arguments must contain exactly: {', '.join(sorted(expected))}")


def _word_count(args: dict[str, Any]) -> dict[str, Any]:
    _require_exact_keys(args, {"text"})
    text = args["text"]
    if not isinstance(text, str):
        raise ToolError("text must be a string")
    return {"words": len(text.split()), "chars": len(text)}


def _unit_convert(args: dict[str, Any]) -> dict[str, Any]:
    _require_exact_keys(args, {"value", "from_unit", "to_unit"})
    value = args["value"]
    from_unit = args["from_unit"]
    to_unit = args["to_unit"]

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ToolError("value must be a number")
    if not isinstance(from_unit, str) or not isinstance(to_unit, str):
        raise ToolError("from_unit and to_unit must be strings")

    source = from_unit.lower()
    target = to_unit.lower()
    conversions: dict[tuple[str, str], Callable[[float], float]] = {
        ("c", "f"): lambda number: (number * 9 / 5) + 32,
        ("f", "c"): lambda number: (number - 32) * 5 / 9,
        ("km", "mi"): lambda number: number * 0.621371192237334,
        ("mi", "km"): lambda number: number * 1.609344,
    }
    conversion = conversions.get((source, target))
    if conversion is None:
        raise ToolError("Supported conversions are c to f, f to c, km to mi, and mi to km")

    return {"value": conversion(float(value)), "unit": target}


TOOLS: dict[str, OfflineTool] = {
    "word_count": OfflineTool(
        name="word_count",
        description="Count the words and characters in text.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        _function=_word_count,
    ),
    "unit_convert": OfflineTool(
        name="unit_convert",
        description="Convert temperatures between c and f or distances between km and mi.",
        input_schema={
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "from_unit": {"type": "string", "enum": ["c", "f", "km", "mi"]},
                "to_unit": {"type": "string", "enum": ["c", "f", "km", "mi"]},
            },
            "required": ["value", "from_unit", "to_unit"],
            "additionalProperties": False,
        },
        _function=_unit_convert,
    ),
}


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call a registered tool or raise a consistent validation error."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool: {name}")
    try:
        return tool.call(args)
    except ToolError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolError(f"Invalid arguments for {name}") from exc
