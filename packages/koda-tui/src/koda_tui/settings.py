from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError
from pydantic_core import PydanticCustomError

from koda_common.settings import (
    BaseSettingsManager,
    SettingsManager,
    SettingsUnknownKeysError,
    SettingsValidationError,
)
from koda_tui.appearance import AUTO, THEMES

if TYPE_CHECKING:
    from koda_common.settings.protocols import JsonObject, SettingsStore


_TUI_SECTION = "tui"


def _validate_theme(value: str) -> str:
    if value not in THEMES:
        choices = ", ".join(f"'{name}'" for name in THEMES)
        raise PydanticCustomError("theme", "Input should be one of {choices}", {"choices": choices})
    return value


_Theme = Annotated[str, AfterValidator(_validate_theme)]


@dataclass(frozen=True, slots=True)
class AppSettings:
    core: SettingsManager
    tui: TuiSettingsManager

    @property
    def proxy_managed(self) -> bool:
        """Whether provider credentials are managed outside Koda, by a proxy."""
        return self.core.credential_mode == "proxy-managed"


class TuiSettings(BaseModel):
    """TUI-only preferences persisted to the ``tui`` config section."""

    model_config = ConfigDict(validate_assignment=True)

    theme: _Theme = Field(default=AUTO.name, description="UI theme")
    show_scrollbar: bool = Field(default=True, description="Show chat scrollbar")
    queue_inputs: bool = Field(default=True, description="Queue inputs during streaming")


class TuiSettingsManager(BaseSettingsManager):
    """Manage TUI-only preferences persisted in the shared config file."""

    def __init__(self, settings_store: SettingsStore) -> None:
        super().__init__()
        self._settings_store = settings_store
        self._settings = self._load_model()

    def __getattr__(self, name: str):
        """Expose TUI settings fields as manager attributes."""

        if name in TuiSettings.model_fields:
            return getattr(self._settings, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: object) -> None:
        """Reject direct writes to managed TUI settings fields."""

        if name != "_settings" and name in TuiSettings.model_fields:
            raise AttributeError(name)
        super().__setattr__(name, value)

    def _load_section_data(self) -> JsonObject:
        persisted = self._settings_store.load_section(_TUI_SECTION)
        unknown_keys = set(persisted) - set(TuiSettings.model_fields)
        if unknown_keys:
            raise SettingsUnknownKeysError(unknown_keys)
        return persisted

    def _load_model(self) -> TuiSettings:
        merged = TuiSettings().model_dump()
        merged.update(self._load_section_data())
        try:
            return TuiSettings.model_validate(merged)
        except ValidationError as error:
            raise SettingsValidationError(error) from error

    def update(self, **changes: object) -> None:
        unknown_fields = [name for name in changes if name not in TuiSettings.model_fields]
        if unknown_fields:
            raise AttributeError(unknown_fields[0])
        if not changes:
            return

        merged = self._settings.model_dump()
        merged.update(changes)
        try:
            updated = TuiSettings.model_validate(merged)
        except ValidationError as error:
            raise SettingsValidationError(error) from error

        changed_fields = self.changed_fields(self._settings, updated, tuple(changes))
        if not changed_fields:
            return

        self._settings = updated
        self._settings_store.save_section(_TUI_SECTION, updated.model_dump(mode="json"))
        self._notify(changed_fields)
