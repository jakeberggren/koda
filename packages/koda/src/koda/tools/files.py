from __future__ import annotations

import codecs
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from anyio import Path as AnyioPath
from anyio import to_thread

from koda.tools import exceptions

if TYPE_CHECKING:
    from pathlib import Path


class TextFileErrorType(Protocol):
    """Callable error type that accepts a tool path and the underlying file failure."""

    def __call__(self, path: str, *, cause: Exception) -> Exception: ...


class TextDecodeError(exceptions.ToolError):
    """Failed to decode a file as UTF-8 text."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"Failed to decode '{path}' as UTF-8 text. "
            "The file may be binary or use an unsupported encoding."
        )


@dataclass(frozen=True, slots=True)
class DecodedText:
    """Decoded file contents together with the encoding used."""

    text: str
    encoding: str


SUPPORTED_TEXT_ENCODINGS = ("utf-8", "utf-8-sig")


def _decode_text(data: bytes, path: str) -> DecodedText:
    """Decode full file contents as UTF-8 text, allowing a UTF-8 BOM."""
    if b"\x00" in data:
        raise TextDecodeError(path)
    for encoding in SUPPORTED_TEXT_ENCODINGS:
        try:
            return DecodedText(text=data.decode(encoding), encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise TextDecodeError(path)


def _detect_text_encoding(sample: bytes, path: str) -> str:
    """Pick the UTF-8 variant to use for text decoding."""
    if b"\x00" in sample:
        raise TextDecodeError(path)
    if sample.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    return "utf-8"


def _read_text_lines_sync(resolved: Path, path: str, offset: int, limit: int) -> DecodedText:
    """Read a bounded line window from a text file using synchronous I/O."""
    with resolved.open("rb") as handle:
        encoding = _detect_text_encoding(handle.read(8192), path)
    try:
        with resolved.open("r", encoding=encoding) as handle:
            lines: list[str] = []
            for line_number, line in enumerate(handle):
                if line_number < offset:
                    continue

                lines.append(line)
                if len(lines) >= limit:
                    break

            return DecodedText(text="".join(lines), encoding=encoding)
    except UnicodeDecodeError as e:
        raise TextDecodeError(path) from e


async def read_text(
    resolved: Path,
    path: str,
    *,
    error: TextFileErrorType,
) -> DecodedText:
    """Read an entire file and decode it as supported text."""
    try:
        data = await AnyioPath(resolved).read_bytes()
    except PermissionError as e:
        raise exceptions.PermissionError(path) from e
    except OSError as e:
        raise error(path, cause=e) from e

    return _decode_text(data, path)


async def read_text_lines(
    resolved: Path,
    path: str,
    *,
    offset: int,
    limit: int,
    error: TextFileErrorType,
) -> DecodedText:
    """Read a bounded range of decoded text lines from a file."""
    try:
        return await to_thread.run_sync(_read_text_lines_sync, resolved, path, offset, limit)
    except PermissionError as e:
        raise exceptions.PermissionError(path) from e
    except OSError as e:
        raise error(path, cause=e) from e


async def write_text(
    resolved: Path,
    path: str,
    content: str,
    *,
    error: TextFileErrorType,
    encoding: str = "utf-8",
) -> None:
    """Write text content to a file, creating parent directories when needed."""
    try:
        await AnyioPath(resolved.parent).mkdir(parents=True, exist_ok=True)
        await AnyioPath(resolved).write_text(content, encoding=encoding)
    except PermissionError as e:
        raise exceptions.PermissionError(path) from e
    except OSError as e:
        raise error(path, cause=e) from e
