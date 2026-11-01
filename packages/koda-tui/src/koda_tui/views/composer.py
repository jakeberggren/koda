"""Composer: where messages are written, with file suggestions for @ mentions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion, ThreadedCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import ConditionalKeyBindings, KeyBindings, merge_key_bindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import ConditionalContainer, VSplit
from prompt_toolkit.widgets import Box

from koda_tui.appearance import Spacing, Tokens
from koda_tui.terminal.keys import ALT_ENTER
from koda_tui.ui.primitives import Editor
from koda_tui.ui.widgets import List, ListItem, ListState, Prompt
from koda_tui.workspace import WorkspaceFiles

if TYPE_CHECKING:
    from collections.abc import Iterator

    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from prompt_toolkit.key_binding import KeyBindingsBase, KeyPressEvent

    from koda_tui.state import AppState

MAX_ROWS = 10  # The composer grows with its text up to this many rows.
SUGGESTIONS = 10  # Most files suggested for an @ mention.


class Submit(Protocol):
    def __call__(self, text: str, /, *, alternate: bool) -> None: ...


class Composer:
    """An editor with a prompt on a raised surface. Typing ``@`` and part of a path
    suggests workspace files; accepting one puts its path after the ``@``.

    The buffer's completer finds the files, off the UI thread. prompt_toolkit only
    completes as characters are typed, so the composer also starts it on any other
    change that leaves the cursor in a mention, such as a backspace or a cursor move.
    The suggestions show in a List with a selection of their own.

    Enter submits the text to ``on_submit``; Alt+Enter too, as the ``alternate`` way.
    Ctrl+J starts a new line. ``suggestions`` is a separate container, so the layout
    can place it above.
    """

    def __init__(self, state: AppState, *, on_submit: Submit) -> None:
        self._suggestions: ListState[str] = ListState([])
        self.buffer = Buffer(
            multiline=True,
            name="input_buffer",
            completer=ThreadedCompleter(MentionCompleter(WorkspaceFiles(state.workspace))),
            on_text_changed=self._follow_mention,
            on_cursor_position_changed=self._follow_mention,
            on_completions_changed=self._show_completions,
        )
        self._editor = Editor(self.buffer, max_height=MAX_ROWS)
        self.suggestions = ConditionalContainer(
            List(self._suggestions),
            filter=Condition(self.is_mentioning),
        )
        self.key_bindings = self._key_bindings(on_submit)
        self._container = Box(
            VSplit([Prompt(), self._editor], padding=Spacing.GAP, key_bindings=self.key_bindings),
            padding=0,
            padding_top=Spacing.GAP,
            padding_bottom=Spacing.GAP,
            padding_left=Spacing.EDGE,
            style=Tokens.Surface.RAISED,
        )

    def __pt_container__(self) -> Box:
        return self._container

    @property
    def text(self) -> str:
        return self.buffer.text

    @text.setter
    def text(self, text: str) -> None:
        self.buffer.text = text
        self.buffer.cursor_position = len(text)

    def _move_up(self, count: int) -> None:
        """Move up by wrapped rows; from the first row, recall earlier history."""
        for _ in range(count):
            if not self._editor.move_cursor(-1) and not self.buffer.selection_state:
                self.buffer.history_backward()

    def _move_down(self, count: int) -> None:
        """Move down by wrapped rows; from the last row, recall later history."""
        for _ in range(count):
            if not self._editor.move_cursor(1) and not self.buffer.selection_state:
                self.buffer.history_forward()

    def is_mentioning(self) -> bool:
        """Whether the cursor is in an @ mention, so suggestions are showing."""
        return _mention(self.buffer.document) is not None

    def has_suggestion(self) -> bool:
        """Whether a suggested file is selected."""
        return self._suggestions.selected_item is not None

    def move_suggestion(self, delta: int) -> None:
        self._suggestions.move_selection(delta, wrap=True)

    def accept_suggestion(self) -> bool:
        """Apply the selected file's completion: its path after the mention's ``@``."""
        selected = self._suggestions.selected_item
        state = self.buffer.complete_state
        if selected is None or state is None:
            return False
        completion = next((c for c in state.completions if c.text == selected.data), None)
        if completion is None:
            return False
        self.buffer.apply_completion(completion)
        return True

    def _key_bindings(self, on_submit: Submit) -> KeyBindingsBase:
        """Writing keys, then the suggestion keys, which take over while suggesting."""
        suggesting = Condition(self.has_suggestion)
        return merge_key_bindings(
            [
                self._writing_keys(on_submit),
                ConditionalKeyBindings(self._suggestion_keys(), suggesting),
            ],
        )

    def _writing_keys(self, on_submit: Submit) -> KeyBindings:  # noqa: C901 - one handler per key
        kb = KeyBindings()

        @kb.add(Keys.Enter)
        def _enter(_event: KeyPressEvent) -> None:
            self._submit(on_submit, alternate=False)

        @kb.add(*ALT_ENTER)
        def _alt_enter(_event: KeyPressEvent) -> None:
            self._submit(on_submit, alternate=True)

        @kb.add(Keys.ControlJ)
        def _newline(_event: KeyPressEvent) -> None:
            self.buffer.insert_text("\n")

        @kb.add(Keys.Up, eager=True)
        def _up(event: KeyPressEvent) -> None:
            self._move_up(event.arg)

        @kb.add(Keys.Down, eager=True)
        def _down(event: KeyPressEvent) -> None:
            self._move_down(event.arg)

        return kb

    def _suggestion_keys(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add(Keys.Up, eager=True)
        def _previous(_event: KeyPressEvent) -> None:
            self.move_suggestion(-1)

        @kb.add(Keys.Down, eager=True)
        def _next(_event: KeyPressEvent) -> None:
            self.move_suggestion(1)

        @kb.add(Keys.Enter, eager=True)
        @kb.add(Keys.Tab, eager=True)
        def _accept(_event: KeyPressEvent) -> None:
            self.accept_suggestion()

        return kb

    def _submit(self, on_submit: Submit, *, alternate: bool) -> None:
        """Hand the text, trimmed, to ``on_submit`` and clear the composer, if there is any."""
        if text := self.text.strip():
            self.buffer.reset()
            on_submit(text, alternate=alternate)

    def _follow_mention(self, buffer: Buffer) -> None:
        """Complete the mention the cursor is in, or drop the suggestions outside one."""
        if not self.is_mentioning():
            self._suggestions.set_items([])
        elif buffer.complete_state is None:
            buffer.start_completion()

    def _show_completions(self, buffer: Buffer) -> None:
        """Show the completions found, keeping the last ones while more are loading."""
        state = buffer.complete_state
        if state is None:
            self._suggestions.set_items([])
        elif state.completions:  # Empty while still loading: keep the last ones till then.
            self._suggestions.set_items(
                [ListItem(label=c.display_text, data=c.text) for c in state.completions],
            )


class MentionCompleter(Completer):
    """Workspace files for the @ mention before the cursor; each puts its path after
    the ``@``, then a space, so the cursor leaves the mention. A new mention, just
    ``@``, looks at the files on disk again."""

    def __init__(self, files: WorkspaceFiles) -> None:
        self._files = files

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,  # noqa: ARG002 - completes the same however asked
    ) -> Iterator[Completion]:
        if (query := _mention(document)) is None:
            return
        if not query:
            self._files.refresh()
        for path in self._files.search(query, SUGGESTIONS):
            yield Completion(f"{path} ", start_position=-len(query), display=path)


def _mention(document: Document) -> str | None:
    """What is typed after the ``@`` of the mention before the cursor, if it's in one."""
    word = document.get_word_before_cursor(WORD=True)
    return word[1:] if word.startswith("@") else None
