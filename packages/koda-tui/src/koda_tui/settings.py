"""Settings: the agent's, and how the TUI looks and takes input, in
``~/.koda/settings.json``."""

from __future__ import annotations

from copy import replace
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError
from pydantic_core import PydanticCustomError

from koda.agent import AgentSettings
from koda.paths import koda_home_dir
from koda_tui.appearance import AUTO, THEMES

if TYPE_CHECKING:
    from pathlib import Path


class SettingsError(Exception):
    """The settings file can't be read, or holds settings Koda doesn't know."""

    def __init__(self, path: Path, error: OSError | ValidationError) -> None:
        if isinstance(error, OSError):
            message = f"Can't read settings from {path}: {error}"
        else:
            problems = (
                f"- {'.'.join(map(str, issue['loc'])) or '<file>'}: {issue['msg']}"
                for issue in error.errors(include_url=False)
            )
            message = "\n".join([f"Invalid settings in {path}", *problems])
        super().__init__(message)
        self.path = path


def _theme(value: str) -> str:
    if value not in THEMES:
        choices = ", ".join(f"'{name}'" for name in THEMES)
        raise PydanticCustomError("theme", "Input should be one of {choices}", {"choices": choices})
    return value


class TuiSettings(BaseModel):
    """How the TUI looks and takes input."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    theme: Annotated[str, AfterValidator(_theme)] = AUTO.name
    show_scrollbar: bool = True
    queue_inputs: bool = True


class Settings(BaseModel):
    """What the user picked: for the agent, and for the TUI. Changed by replacing it,
    through ``with_agent`` and ``with_tui``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent: AgentSettings = Field(default_factory=AgentSettings)
    tui: TuiSettings = Field(default_factory=TuiSettings)

    def with_agent(self, **changes: Any) -> Settings:
        """These settings, with ``changes`` to the agent's."""
        return replace(self, agent=replace(self.agent, **changes))

    def with_tui(self, **changes: Any) -> Settings:
        """These settings, with ``changes`` to the TUI's."""
        return replace(self, tui=replace(self.tui, **changes))

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        """The settings in ``path``, or the defaults when there is no file yet."""
        path = path or _default_path()
        try:
            return cls.model_validate_json(path.read_bytes())
        except FileNotFoundError:
            return cls()
        except (OSError, ValidationError) as error:
            raise SettingsError(path, error) from error

    def save(self, path: Path | None = None) -> None:
        path = path or _default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")


def _default_path() -> Path:
    return koda_home_dir() / "settings.json"
