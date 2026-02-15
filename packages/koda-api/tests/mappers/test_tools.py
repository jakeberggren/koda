from koda.tools import ToolCall as CoreToolCall
from koda.tools import ToolOutput as CoreToolOutput
from koda.tools import ToolResult as CoreToolResult
from koda_api.mappers import (
    map_tool_call_to_contract_tool_call,
    map_tool_output_to_contract_tool_output,
    map_tool_result_to_contract_tool_result,
)


def test_map_tool_call_to_contract_tool_call() -> None:
    core_tool_call = CoreToolCall(tool_name="read_file", arguments={"path": "/tmp/a"}, call_id="c1")

    mapped = map_tool_call_to_contract_tool_call(core_tool_call)

    assert mapped.tool_name == "read_file"
    assert mapped.arguments == {"path": "/tmp/a"}
    assert mapped.call_id == "c1"


def test_map_tool_output_to_contract_tool_output() -> None:
    core_tool_output = CoreToolOutput(
        content={"result": "ok"},
        display="ok",
        is_error=False,
        error_message=None,
    )

    mapped = map_tool_output_to_contract_tool_output(core_tool_output)

    assert mapped.content == {"result": "ok"}
    assert mapped.display == "ok"
    assert mapped.is_error is False
    assert mapped.error_message is None


def test_map_tool_result_to_contract_tool_result() -> None:
    core_tool_result = CoreToolResult(
        call_id="c2",
        output=CoreToolOutput(is_error=True, error_message="boom"),
    )

    mapped = map_tool_result_to_contract_tool_result(core_tool_result)

    assert mapped.call_id == "c2"
    assert mapped.output.is_error is True
    assert mapped.output.error_message == "boom"
