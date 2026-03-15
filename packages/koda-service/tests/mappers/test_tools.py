from koda.tools import ToolCall as CoreToolCall
from koda.tools import ToolOutput as CoreToolOutput
from koda.tools import ToolResult as CoreToolResult
from koda_service.mappers import (
    map_tool_call_to_contract_tool_call,
    map_tool_output_to_contract_tool_output,
    map_tool_result_to_contract_tool_result,
)


def test_map_tool_call_to_contract_tool_call() -> None:
    core_call = CoreToolCall(
        tool_name="read_file",
        arguments={"path": "README.md", "offset": 0},
        call_id="call-123",
    )

    contract_call = map_tool_call_to_contract_tool_call(core_call)

    assert contract_call.tool_name == "read_file"
    assert contract_call.arguments == {"path": "README.md", "offset": 0}
    assert contract_call.call_id == "call-123"


def test_map_tool_output_to_contract_tool_output() -> None:
    core_output = CoreToolOutput(
        content={"text": "hello"},
        display="hello",
        is_error=True,
        error_message="boom",
    )

    contract_output = map_tool_output_to_contract_tool_output(core_output)

    assert contract_output.content == {"text": "hello"}
    assert contract_output.display == "hello"
    assert contract_output.is_error is True
    assert contract_output.error_message == "boom"


def test_map_tool_result_to_contract_tool_result() -> None:
    core_result = CoreToolResult(
        output=CoreToolOutput(content={"ok": True}),
        call_id="call-456",
    )

    contract_result = map_tool_result_to_contract_tool_result(core_result)

    assert contract_result.call_id == "call-456"
    assert contract_result.output.content == {"ok": True}
    assert contract_result.output.display is None
