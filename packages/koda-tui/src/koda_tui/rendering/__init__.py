"""Rendering: content (messages, markdown, tool calls, diffs) as styled fragments.

Rendering only produces fragments; views lay them out. Content is built as Rich
renderables, and ``rendering.rich`` renders them as fragments styled by tokens.
"""

from koda_tui.rendering.renderer import Renderer

__all__ = ["Renderer"]
