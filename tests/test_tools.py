import pytest

from agentsvc.tools import ToolError, call_tool


def test_word_count() -> None:
    assert call_tool("word_count", {"text": "small offline demo"}) == {
        "words": 3,
        "chars": 18,
    }


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"value": 0, "from_unit": "c", "to_unit": "f"}, {"value": 32.0, "unit": "f"}),
        (
            {"value": 1, "from_unit": "mi", "to_unit": "km"},
            {"value": 1.609344, "unit": "km"},
        ),
    ],
)
def test_unit_convert(arguments: dict[str, object], expected: dict[str, object]) -> None:
    assert call_tool("unit_convert", arguments) == expected


def test_unknown_tool_is_an_error() -> None:
    with pytest.raises(ToolError, match="Unknown tool"):
        call_tool("missing", {})


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("word_count", {"text": 12}),
        ("unit_convert", {"value": 1, "from_unit": "kg", "to_unit": "lb"}),
    ],
)
def test_bad_tool_arguments_are_errors(name: str, arguments: dict[str, object]) -> None:
    with pytest.raises(ToolError):
        call_tool(name, arguments)
