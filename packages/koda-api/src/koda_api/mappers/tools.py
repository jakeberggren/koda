from koda.tools import ToolCall as CoreToolCall
from koda.tools import ToolOutput as CoreToolOutput
from koda.tools import ToolResult as CoreToolResult
from koda_common.contracts import ToolCall, ToolOutput, ToolResult


def map_tool_call_to_contract_tool_call(core_tool_call: CoreToolCall) -> ToolCall:
    """Map core tool call to contract tool call."""
    return ToolCall(
        tool_name=core_tool_call.tool_name,
        arguments=core_tool_call.arguments,
        call_id=core_tool_call.call_id,
    )


def map_tool_output_to_contract_tool_output(core_tool_output: CoreToolOutput) -> ToolOutput:
    """Map core tool output to contract tool output."""
    return ToolOutput(
        content=core_tool_output.content,
        display=core_tool_output.display,
        is_error=core_tool_output.is_error,
        error_message=core_tool_output.error_message,
    )


def map_tool_result_to_contract_tool_result(core_tool_result: CoreToolResult) -> ToolResult:
    """Map core tool result to contract tool result."""
    return ToolResult(
        output=map_tool_output_to_contract_tool_output(core_tool_result.output),
        call_id=core_tool_result.call_id,
    )
