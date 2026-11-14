from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest

from koda.llm.auth.callback import OAuthCallbackListener
from koda.llm.auth.exceptions import OAuthCallbackCodeMissingError, OAuthCallbackTimeoutError


@pytest.fixture
def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _read_url(url: str) -> tuple[int, str]:
    deadline = monotonic() + 2
    while True:
        try:
            with urlopen(url, timeout=0.05) as response:  # noqa: S310
                return response.status, response.read().decode("utf-8")
        except HTTPError as error:
            return error.code, error.read().decode("utf-8")
        except URLError:
            if monotonic() >= deadline:
                raise
            sleep(0.01)


def test_receive_callback_returns_authorization_code(free_port: int) -> None:
    listener = OAuthCallbackListener(
        port=free_port,
        callback_path="/auth/callback",
        state="expected-state",
        timeout=2,
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(listener.receive)

        status, body = _read_url(
            f"http://127.0.0.1:{free_port}/auth/callback?code=auth-code&state=expected-state"
        )

    assert status == 200
    assert "Authentication complete" in body
    assert future.result(timeout=1) == "auth-code"


def test_receive_callback_ignores_state_mismatch_and_accepts_valid_callback(free_port: int) -> None:
    listener = OAuthCallbackListener(
        port=free_port,
        callback_path="/auth/callback",
        state="expected-state",
        timeout=2,
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(listener.receive)

        status, body = _read_url(
            f"http://127.0.0.1:{free_port}/auth/callback?code=auth-code&state=wrong-state"
        )
        valid_status, valid_body = _read_url(
            f"http://127.0.0.1:{free_port}/auth/callback?code=valid-code&state=expected-state"
        )

    assert status == 400
    assert "State mismatch" in body
    assert valid_status == 200
    assert "Authentication complete" in valid_body
    assert future.result(timeout=1) == "valid-code"


def test_receive_callback_raises_on_missing_code(free_port: int) -> None:
    listener = OAuthCallbackListener(
        port=free_port,
        callback_path="/auth/callback",
        state="expected-state",
        timeout=2,
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(listener.receive)

        status, body = _read_url(f"http://127.0.0.1:{free_port}/auth/callback?state=expected-state")

    assert status == 400
    assert "Missing authorization code" in body
    with pytest.raises(OAuthCallbackCodeMissingError):
        future.result(timeout=1)


def test_receive_callback_times_out(free_port: int) -> None:
    listener = OAuthCallbackListener(
        port=free_port,
        callback_path="/auth/callback",
        state="expected-state",
        timeout=0.01,
    )

    with pytest.raises(OAuthCallbackTimeoutError):
        listener.receive()


def test_listener_starts_without_a_reverse_dns_lookup(
    free_port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_lookup(name: str = "") -> str:
        raise AssertionError(f"unexpected reverse DNS lookup for {name!r}")

    monkeypatch.setattr(socket, "getfqdn", _no_lookup)
    listener = OAuthCallbackListener(
        port=free_port,
        callback_path="/auth/callback",
        state="expected-state",
        timeout=2,
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(listener.receive)

        status, _ = _read_url(
            f"http://127.0.0.1:{free_port}/auth/callback?code=auth-code&state=expected-state"
        )

    assert status == 200
    assert future.result(timeout=1) == "auth-code"
