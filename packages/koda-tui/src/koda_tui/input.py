from typing import Protocol

from prompt_toolkit import PromptSession
from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.validation import ValidationError, Validator


class InputHandler(Protocol):
    """Protocol for handling user input."""

    async def get_input(self, prompt: str = "") -> str:
        """Get input from the user."""
        ...


class NonEmptyValidator(Validator):
    """Validator that rejects empty input."""

    def validate(self, document) -> None:
        text = document.text.strip()
        if not text:
            raise ValidationError()


class PromptToolkitInput(InputHandler):
    """Input handler using prompt_toolkit with multiline support."""

    def __init__(self) -> None:
        self._setup_key_bindings()

    def _setup_key_bindings(self) -> None:
        # Register Ghostty's Ctrl+Enter sequence to ControlJ
        # TODO: Check how other terminals handle this and implement
        # other sequences that should be mapped to ControlJ
        ANSI_SEQUENCES["\x1b[27;5;13~"] = Keys.ControlJ

        self._kb = KeyBindings()

        @self._kb.add(Keys.Enter)
        def _(event):
            event.current_buffer.validate_and_handle()

        @self._kb.add(Keys.ControlJ)  # Handles both Ctrl+J and Ghostty's Ctrl+Enter
        def _(event):
            event.current_buffer.insert_text("\n")

        @self._kb.add(Keys.Escape, Keys.Enter)  # Alt+Enter fallback
        def _(event):
            event.current_buffer.insert_text("\n")

    async def get_input(self, prompt: str = "") -> str:
        """
        Get multiline input where:
        - Enter submits
        - Ctrl+Enter adds newline (Ghostty/modern terminals)
        - Alt+Enter adds newline (fallback)
        """
        session = PromptSession(
            multiline=True,
            key_bindings=self._kb,
            validator=NonEmptyValidator(),
        )
        return await session.prompt_async(prompt)
