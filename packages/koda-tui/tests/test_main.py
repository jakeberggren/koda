from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from koda_service.exceptions import StartupConfigurationError
from koda_tui import _report_startup_error, main

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger


class _LoggerStub:
    def error(self, _event: str, **_kwargs: object) -> None:
        return


def test_report_startup_error_logs_and_prints(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _report_startup_error(
        StartupConfigurationError(
            "Invalid configuration",
            details=("theme: Input should be 'dark' or 'light'",),
        ),
        cast("BoundLogger", _LoggerStub()),
    )

    captured = capsys.readouterr()
    assert captured.err == (
        "Application failed to start (StartupConfigurationError): "
        "Invalid configuration\n- theme: Input should be 'dark' or 'light'\n"
    )


def test_main_prints_startup_error_and_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "koda_tui.create_startup_context",
        lambda _cwd: (_ for _ in ()).throw(
            StartupConfigurationError(
                "Invalid configuration",
                details=("theme: Input should be 'dark' or 'light'",),
            )
        ),
    )
    monkeypatch.setattr("koda_tui.configure_logging", lambda _config: None)
    monkeypatch.setattr("koda_tui._report_startup_error", lambda _error, _logger: None)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
