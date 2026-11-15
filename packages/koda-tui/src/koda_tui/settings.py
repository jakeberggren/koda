"""Settings: the agent's, and how the TUI looks and takes input, in
``~/.koda/settings.json``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError
from pydantic_core import PydanticCustomError

from koda.llm import LLMOptions, ThinkingOptionId
from koda.paths import koda_home_dir
from koda_tui.appearance import AUTO, THEMES

if TYPE_CHECKING:
    from pathlib import Path

    from koda.llm import Model


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


class AgentSettings(BaseModel):
    """The model the agent uses, and how it asks it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str | None = None
    model: str | None = None
    thinking: ThinkingOptionId = "none"
    web_search: bool = False
    extended_prompt_retention: bool = False

    def request_options(self, model: Model) -> LLMOptions:
        """The options to ask ``model`` with: the thinking level it supports nearest
        the one picked."""
        return LLMOptions(
            thinking=model.thinking.resolve(self.thinking).id,
            web_search=self.web_search,
            extended_prompt_retention=self.extended_prompt_retention,
        )


class TuiSettings(BaseModel):
    """How the TUI looks and takes input."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    theme: Annotated[str, AfterValidator(_theme)] = AUTO.name
    show_scrollbar: bool = True
    queue_inputs: bool = True


class Settings(BaseModel):
    """What the user picked: for the agent, and for the TUI. Changed by replacing it::

    agent_settings = replace(settings.agent_settings, thinking="high")
    settings = replace(settings, agent_settings=agent_settings)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_settings: AgentSettings = Field(default_factory=AgentSettings)
    tui_settings: TuiSettings = Field(default_factory=TuiSettings)

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
