"""Rendering: content (messages, markdown, tool calls, diffs) as styled fragments.

Rendering only produces fragments; views lay them out.
"""

from koda_tui.rendering.messages import render_message

__all__ = ["render_message"]
