"""Strings: every piece of text the TUI shows, grouped by where it is shown.

Import the module and read through it: ``strings.Screen.Status.READY``. Text that
varies is a function next to the constants it belongs with, so plurals and wording
stay here too. Key names are written in lowercase, joined with ``+``: ``ctrl+d``,
``alt+enter``.

This module imports nothing from Koda, so every layer can use it.
"""

from __future__ import annotations

from typing import ClassVar


class Key:
    """Key names, as shown in hints."""

    ALT_ENTER = "alt+enter"
    ALT_UP = "alt+up"
    CTRL_C = "ctrl+c"
    CTRL_D = "ctrl+d"
    CTRL_N = "ctrl+n"
    CTRL_P_K = "ctrl+p/k"
    CTRL_T = "ctrl+t"
    ENTER = "enter"
    ESC = "esc"


class Common:
    """Text not tied to a single screen or menu."""

    ELLIPSIS = "..."
    NO_MATCHES = "No matches"
    YES = "Yes"
    NO = "No"


class App:
    """Outside the TUI: what is printed when Koda can't start."""

    @staticmethod
    def failed_to_start(error: object) -> str:
        return f"Koda failed to start: {error}"


class Screen:
    """What is always on screen: the conversation, waiting messages, the status bar."""

    class Chat:
        """The conversation."""

        ERROR_FALLBACK = "Complete the required setup and try again."

        class Tools:
            """Tool calls and their results."""

            SUCCEEDED = "succeeded"
            STDERR_EMPTY = "stderr empty"
            STDOUT = "stdout:"
            STDERR = "stderr:"

            @staticmethod
            def exited(code: object) -> str:
                return f"exit {code}"

            @staticmethod
            def stdout_lines(count: int) -> str:
                return f"stdout {_count(count, 'line')}"

            @staticmethod
            def stderr_lines(count: int) -> str:
                return f"stderr {_count(count, 'line')}"

            @staticmethod
            def long_value(chars: int, lines: int) -> str:
                """A long or multi-line argument, in place of its value."""
                return f"[{_count(chars, 'char')}, {_count(lines, 'line')}]"

            @staticmethod
            def truncated(lines: int) -> str:
                return f"[truncated, {_count(lines, 'line')} in total]"

            @staticmethod
            def diff_summary(additions: int, deletions: int) -> str:
                return f"{_count(additions, 'addition')}, {_count(deletions, 'deletion')}"

    class Pending:
        """Messages waiting while a response runs."""

        STEERING = "steering: "

        @staticmethod
        def queued(count: int) -> str:
            hint = f"{Key.ESC} to send now, {Key.ALT_UP} to edit"
            return f"{_count(count, 'message')} queued ({hint})"

    class Status:
        """The status bar, and the activity indicator above the composer."""

        ACTIVITY = f"Working{Common.ELLIPSIS} ({Key.ESC} to interrupt)"
        READY = "ready"
        THINKING = "thinking"
        RESPONDING = "responding"
        WORKING = "working"
        RUNNING_TOOLS = "running tools"
        EXIT_AGAIN = f"press {Key.CTRL_C} again to exit"
        INPUT_TOKENS = "in"
        OUTPUT_TOKENS = "out"
        PALETTE = "palette"
        CYCLE_THINKING = "thinking"

        @staticmethod
        def context(percentage: int) -> str:
            return f"ctx {percentage}%"


class Palette:
    """The command palette, and the menus its commands open."""

    TITLE = "Commands"

    class Groups:
        """The headings commands are listed under."""

        AGENT = "Agent"
        SESSIONS = "Sessions"
        APPEARANCE = "Appearance"
        SYSTEM = "System"

    class Command:
        """What every command shows in the palette: its label, which is also the title
        of the menu it opens, and a detail beside it."""

        TITLE: ClassVar[str]
        DETAIL: ClassVar[str]

    class Providers(Command):
        TITLE = "Connect Provider"
        DETAIL = "Add an API key or log in to a provider"
        HEADING = "Choose a provider"
        PROXY_MANAGED_HEADING = "Available providers"
        CONNECTIONS_HEADING = "Connect using"
        PROXY_MANAGED = (
            "Credentials are managed by a proxy: set them with sbx secret set outside Koda. "
            "Connections are checked when you send a message."
        )
        LOGIN_FAILED = "Provider login failed"

        @staticmethod
        def enter(label: str) -> str:
            """The title asking for a credential, such as an API key."""
            return f"Enter {label}"

        @staticmethod
        def connecting(provider: str, label: str) -> str:
            return f"Connecting {provider} ({label})"

    class Thinking(Command):
        TITLE = "Set Thinking Level"
        DETAIL = "Choose how much the model reasons"
        HEADING = "Choose a reasoning effort"

    class Models(Command):
        TITLE = "Switch Model"
        DETAIL = "Choose a different model"
        PROXY_MANAGED = (
            "Credentials are managed by a proxy: model access is checked when you send a message."
        )

    class NewSession(Command):
        TITLE = "New Session"
        DETAIL = "Start a new conversation"

    class Sessions(Command):
        TITLE = "Switch Session"
        DETAIL = "Resume or delete an earlier session"
        HEADING = "Choose a session"
        NEW_HINT = "new"
        DELETE_HINT = "delete"
        CONFIRM_DELETE = "Delete this session?"

        @staticmethod
        def label(name: str, date: str, messages: int) -> str:
            return f"{name}  [{date}] ({_count(messages, 'message')})"

    class Themes(Command):
        TITLE = "Select Theme"
        DETAIL = "Choose auto, light, or dark"
        HEADING = "Choose a theme"
        AUTO = "Auto"
        AUTO_DETAIL = "Match the terminal's background"
        DARK = "Terminal Dark"
        DARK_DETAIL = "Terminal colors for dark backgrounds"
        LIGHT = "Terminal Light"
        LIGHT_DETAIL = "Terminal colors for light backgrounds"

    class Scrollbar(Command):
        TITLE = "Toggle Scrollbar"
        DETAIL = "Show or hide the chat scrollbar"

    class InputMode(Command):
        TITLE = "Input Mode"
        DETAIL = f"Choose what {Key.ENTER} does while Koda responds"
        HEADING = f"What {Key.ENTER} does while Koda responds"
        STEER = "Prefer steer"
        STEER_DETAIL = f"{Key.ENTER} steers, {Key.ALT_ENTER} queues"
        QUEUE = "Prefer queue"
        QUEUE_DETAIL = f"{Key.ENTER} queues, {Key.ALT_ENTER} steers"


def _count(count: int, noun: str) -> str:
    """``count`` and ``noun``, plural unless there is one: "1 line", "2 lines"."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
