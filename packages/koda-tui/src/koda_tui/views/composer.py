"""Composer: where messages are written, with file suggestions for @ mentions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import ConditionalContainer, HSplit, VSplit, Window

from koda_tui.appearance import Spacing, Tokens
from koda_tui.ui.primitives import Editor, List, ListItem, ListState, Spacer
from koda_tui.ui.widgets import Prompt
from koda_tui.workspace import WorkspaceFiles

if TYPE_CHECKING:
    from koda_tui.state import AppState

MAX_ROWS = 10  # The composer grows with its text up to this many rows.
SUGGESTIONS = 10  # Most files suggested for an @ mention.


class Composer:
    """An editor with a prompt on a raised surface. Typing ``@`` and part of a path
    suggests workspace files; accepting one replaces the mention with its path.

    ``suggestions`` is a separate container, so the layout can place it above.
    """

    def __init__(self, state: AppState) -> None:
        self._files = WorkspaceFiles(state.workspace)
        self._suggestions: ListState[str] = ListState([])
        self._mention: tuple[int, int] | None = None  # Text range of the @ mention.
        self.buffer = Buffer(
            multiline=True,
            name="input_buffer",
            on_text_changed=self._update_mention,
            on_cursor_position_changed=self._update_mention,
        )
        self._editor = Editor(self.buffer, max_height=MAX_ROWS)
        self.suggestions = ConditionalContainer(
            List(self._suggestions, empty_message="no matches"),
            filter=Condition(lambda: self.is_mentioning),
        )
        self._container = HSplit(
            [
                Spacer(),
                VSplit(
                    [
                        Window(width=Spacing.EDGE),
                        Prompt(),
                        Window(width=Spacing.GAP),
                        self._editor,
                    ],
                ),
                Spacer(),
            ],
            style=Tokens.Surface.RAISED,
        )

    def __pt_container__(self) -> HSplit:
        return self._container

    @property
    def text(self) -> str:
        return self.buffer.text

    @text.setter
    def text(self, text: str) -> None:
        self.buffer.text = text
        self.buffer.cursor_position = len(text)

    def clear(self) -> None:
        self.buffer.reset()

    def move_cursor_up(self, count: int = 1) -> None:
        """Move up by wrapped rows; from the first row, recall earlier history."""
        for _ in range(count):
            if not self._editor.move_cursor(-1):
                self.buffer.auto_up()

    def move_cursor_down(self, count: int = 1) -> None:
        """Move down by wrapped rows; from the last row, recall later history."""
        for _ in range(count):
            if not self._editor.move_cursor(1):
                self.buffer.auto_down()

    @property
    def is_mentioning(self) -> bool:
        """Whether the cursor is in an @ mention, so suggestions are showing."""
        return self._mention is not None

    @property
    def has_suggestion(self) -> bool:
        """Whether a suggested file is selected."""
        return self._suggestions.selected_item is not None

    def move_suggestion(self, delta: int) -> None:
        self._suggestions.move_selection(delta, wrap=True)

    def accept_suggestion(self) -> bool:
        """Replace the @ mention with the selected file's path."""
        selected = self._suggestions.selected_item
        if selected is None or self._mention is None:
            return False
        start, end = self._mention
        before, after = self.buffer.text[:start], self.buffer.text[end:]
        self.buffer.set_document(
            Document(
                text=f"{before}{selected.label}{after}",
                cursor_position=len(before) + len(selected.label),
            ),
            bypass_readonly=True,
        )
        self._close_suggestions()
        return True

    def _update_mention(self, buffer: Buffer) -> None:
        """Follow the @ mention at the cursor, refreshing the suggested files."""
        mention = _mention_at(buffer.text, buffer.cursor_position)
        if mention is None:
            self._close_suggestions()
            return
        if not self.is_mentioning:
            self._files.refresh()
        start, end, query = mention
        self._mention = (start, end)
        paths = self._files.search(query, SUGGESTIONS)
        self._suggestions.set_items([ListItem(label=path, data=path) for path in paths])

    def _close_suggestions(self) -> None:
        self._mention = None
        self._suggestions.set_items([])


def _mention_at(text: str, cursor: int) -> tuple[int, int, str] | None:
    """The @ mention around ``cursor``, as (start, end, query), if there is one."""
    start = cursor
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    end = cursor
    while end < len(text) and not text[end].isspace():
        end += 1
    word = text[start:end]
    return (start, end, word[1:]) if word.startswith("@") else None
