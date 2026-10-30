from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue
from time import monotonic
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from koda.llm.auth.exceptions import (
    OAuthCallbackCancelledError,
    OAuthCallbackCodeMissingError,
    OAuthCallbackError,
    OAuthCallbackStateError,
    OAuthCallbackTimeoutError,
)
from koda_common.logging import get_logger

log = get_logger(__name__)

if TYPE_CHECKING:
    from socket import socket
    from socketserver import BaseServer
    from threading import Event


type OAuthCallbackResult = str | OAuthCallbackError


def extract_callback_code(query: str, *, expected_state: str) -> str:
    """Extract an OAuth authorization code from callback query parameters."""

    params = parse_qs(query)
    state = params.get("state", [None])[0]
    if state != expected_state:
        raise OAuthCallbackStateError

    code = params.get("code", [None])[0]
    if not code:
        raise OAuthCallbackCodeMissingError

    return code


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle the OAuth redirect request and publish the authorization code."""

    def __init__(
        self,
        request: socket | tuple[bytes, socket],
        client_address: tuple[str, int],
        server: BaseServer,
        *,
        listener: OAuthCallbackListener,
        result: Queue[OAuthCallbackResult],
    ) -> None:
        # The base initializer handles the request, so configure the handler first.
        self.listener = listener
        self.result = result
        super().__init__(request, client_address, server)

    def _send_text(self, status: int, body: str) -> None:
        """Send a short plain-text response to the browser."""
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        """Validate the callback request and write the result to the server queue."""
        url = urlparse(self.path)
        log.info("oauth_callback_request_received", path=url.path)

        if url.path != self.listener.callback_path:
            log.info(
                "oauth_callback_path_mismatch",
                expected=self.listener.callback_path,
                got=url.path,
            )
            self._send_text(404, "Not found")
            return

        try:
            code = extract_callback_code(url.query, expected_state=self.listener.state)
        except OAuthCallbackStateError:
            log.warning("oauth_callback_state_mismatch", expected_prefix=self.listener.state[:8])
            self._send_text(400, "State mismatch")
            return
        except OAuthCallbackCodeMissingError as error:
            params = parse_qs(url.query)
            log.warning("oauth_callback_missing_code", error=params.get("error"))
            self._send_text(400, "Missing authorization code")
            self.result.put(error)
            return

        log.info("oauth_callback_success")
        self._send_text(200, "Authentication complete. You can close this window.")
        self.result.put(code)

    def log_message(self, format: str, *args: object) -> None:  # noqa: ARG002
        """Suppress BaseHTTPRequestHandler's default stderr access logs."""
        return


@dataclass(frozen=True, slots=True, kw_only=True)
class OAuthCallbackListener:
    """One-shot localhost listener for an OAuth redirect."""

    port: int
    callback_path: str
    state: str
    host: str = "127.0.0.1"
    timeout: float = 300
    poll_interval: float = 0.25

    def _wait_for_result(
        self,
        *,
        server: ThreadingHTTPServer,
        result: Queue[OAuthCallbackResult],
        cancel_event: Event | None,
    ) -> OAuthCallbackResult:
        deadline = monotonic() + self.timeout
        while result.empty():
            if cancel_event is not None and cancel_event.is_set():
                raise OAuthCallbackCancelledError
            if monotonic() >= deadline:
                log.warning("oauth_callback_server_timeout", timeout=self.timeout)
                raise OAuthCallbackTimeoutError
            server.handle_request()

        try:
            return result.get_nowait()
        except Empty as error:
            log.warning("oauth_callback_server_empty_result")
            raise OAuthCallbackTimeoutError from error

    def receive(self, *, cancel_event: Event | None = None) -> str:
        """Listen for one OAuth callback and return the authorization code."""

        log.info(
            "oauth_callback_server_starting",
            host=self.host,
            port=self.port,
            path=self.callback_path,
        )
        result: Queue[OAuthCallbackResult] = Queue(maxsize=1)
        handler = partial(
            OAuthCallbackHandler,
            listener=self,
            result=result,
        )
        server = ThreadingHTTPServer((self.host, self.port), handler)
        server.timeout = self.poll_interval
        try:
            value = self._wait_for_result(
                server=server,
                result=result,
                cancel_event=cancel_event,
            )
        finally:
            log.info("oauth_callback_server_closing")
            server.server_close()
        if isinstance(value, OAuthCallbackError):
            log.warning("oauth_callback_server_result_exception", error=repr(value))
            raise value
        log.info("oauth_callback_server_returning_code")
        return value
