"""Stream separation and I/O utilities for Abby CLI.

Enforces Unix composability:
- sys.stdout is reserved exclusively for requested data payloads (paths or JSON).
- sys.stderr is used for diagnostic logs, progress messages, warnings, and errors.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Generator


def output_payload(payload: Any, json_mode: bool = False) -> None:
    """Print payload to standard output (stdout).

    If json_mode is True, formats as indented JSON.
    Otherwise, converts strings or objects to plain text.
    Automatically serializes dataclasses and objects with a to_dict() method.
    """
    if hasattr(payload, "to_dict") and callable(payload.to_dict):
        payload = payload.to_dict()
    elif dataclasses.is_dataclass(payload) and not isinstance(payload, type):
        payload = dataclasses.asdict(payload)

    if json_mode:
        if isinstance(payload, str):
            # If already a JSON string, ensure it's valid or wrap it
            try:
                parsed = json.loads(payload)
                sys.stdout.write(json.dumps(parsed, indent=2, default=str) + "\n")
            except Exception:
                sys.stdout.write(
                    json.dumps({"output": payload}, indent=2, default=str) + "\n"
                )
        else:
            sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")
    else:
        if isinstance(payload, (dict, list)):
            sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")
        else:
            sys.stdout.write(f"{payload}\n")
    sys.stdout.flush()


def log_info(message: str) -> None:
    """Print an informational diagnostic message to stderr."""
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def log_warn(message: str) -> None:
    """Print a warning message to stderr."""
    sys.stderr.write(f"[WARN] {message}\n")
    sys.stderr.flush()


def log_error(message: str) -> None:
    """Print an error message to stderr."""
    sys.stderr.write(f"[ERROR] {message}\n")
    sys.stderr.flush()


@contextmanager
def atomic_write_stream(
    file_path: Path,
    encoding: str = "utf-8",
) -> Generator[IO[str], None, None]:
    """Context manager yielding a temporary writable file stream that atomically replaces destination on exit.

    Writes to a temporary sibling file in file_path.parent, flushes and syncs
    file buffers via os.fsync, closes the stream, and replaces the target file via atomic os.replace.

    Args:
        file_path: Target path to write or replace.
        encoding: Text encoding (default: 'utf-8').

    Yields:
        A writable text stream.

    Raises:
        OSError: If directory creation, file writing, or replacement fails.
                 The temporary file is guaranteed to be unlinked on error,
                 leaving the original target file untouched.
    """
    target_dir = file_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        dir=target_dir,
        encoding=encoding,
        delete=False,
        prefix=f".tmp_{file_path.name}_",
    )
    try:
        yield temp_file
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        os.replace(temp_file.name, file_path)
    except Exception:
        temp_file.close()
        if os.path.exists(temp_file.name):
            try:
                os.remove(temp_file.name)
            except OSError:
                pass
        raise


def atomic_write_text(file_path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically write text content to a destination file on disk.

    Writes to a temporary sibling file in file_path.parent, flushes and syncs
    file buffers via os.fsync, and replaces the target file via atomic os.replace.

    Args:
        file_path: Target path to write or replace.
        content: Text content to write.
        encoding: Text encoding (default: 'utf-8').

    Raises:
        OSError: If directory creation, file writing, or replacement fails.
                 The temporary file is guaranteed to be unlinked on error,
                 leaving the original target file untouched.
    """
    with atomic_write_stream(file_path, encoding=encoding) as stream:
        stream.write(content)

