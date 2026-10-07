# SPDX-License-Identifier: MPL-2.0
"""Locate and identify the external applications ODFA11y drives."""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from odfa11y.errors import ToolNotFoundError

IDENTIFY_TIMEOUT_SECONDS = 20
MAX_OUTPUT_BYTES = 64 * 1024
READ_CHUNK_BYTES = 64 * 1024
READER_JOIN_SECONDS = 5
VERSION_RE = re.compile(r"\d+(?:\.\d+)+")


@dataclass(frozen=True, slots=True)
class ToolRun:
    """A finished external process: its status and the head of each output stream."""

    returncode: int
    stdout: str
    stderr: str
    truncated: bool


def run_bounded(
    command: list[str], *, timeout: float, max_output: int = MAX_OUTPUT_BYTES
) -> ToolRun:
    """Run a program with a time limit and bounded output capture.

    Each output stream keeps only its first ``max_output`` bytes and the rest is drained and
    discarded, so a chatty or hostile program cannot exhaust memory. On timeout the whole
    process tree is killed where the platform allows it.

    Returns
    -------
    ToolRun
        The exit status and the captured heads of stdout and stderr.

    Raises
    ------
    subprocess.TimeoutExpired
        The program did not finish in time and was killed.

    """
    with subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    ) as process:
        captured = [_Capture(process.stdout, max_output), _Capture(process.stderr, max_output)]
        threads = [threading.Thread(target=capture.drain, daemon=True) for capture in captured]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            process.wait()
            raise
        finally:
            for thread in threads:
                thread.join(READER_JOIN_SECONDS)
    return ToolRun(
        process.returncode,
        captured[0].text(),
        captured[1].text(),
        any(capture.truncated for capture in captured),
    )


class _Capture:
    def __init__(self, stream: IO[bytes] | None, limit: int) -> None:
        self._stream = stream
        self._limit = limit
        self._head = bytearray()
        self.truncated = False

    def drain(self) -> None:
        if self._stream is None:
            return
        try:
            while chunk := self._stream.read(READ_CHUNK_BYTES):
                room = self._limit - len(self._head)
                self._head += chunk[: max(room, 0)]
                self.truncated = self.truncated or len(chunk) > room
        except OSError, ValueError:
            return  # the pipe was closed under us after the process ended

    def text(self) -> str:
        return self._head.decode("utf-8", errors="replace")


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
    process.kill()


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    """Name and version of an application as it reports itself."""

    name: str
    version: str

    def as_dict(self) -> dict[str, str]:
        """Serialize the identity.

        Returns
        -------
        dict[str, str]
            The tool name and version.

        """
        return {"name": self.name, "version": self.version}


def find_executable(requested: str | Path | None, candidates: tuple[str, ...]) -> str:
    """Resolve an explicit path or program name, or search the candidate names on PATH.

    Returns
    -------
    str
        The executable's path.

    Raises
    ------
    ToolNotFoundError
        The requested executable, or every candidate, cannot be found.

    """
    if requested is not None:
        path = Path(requested)
        if path.is_file():
            if not os.access(path, os.X_OK):
                msg = f"Not executable: {requested}"
                raise ToolNotFoundError(msg)
            return str(path)
        resolved = shutil.which(str(requested))
        if resolved:
            return resolved
        msg = f"Executable not found: {requested}"
        raise ToolNotFoundError(msg)
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    msg = f"None of {', '.join(candidates)} was found on PATH."
    raise ToolNotFoundError(msg)


def identify(name: str, executable: str, version_args: tuple[str, ...]) -> ToolIdentity:
    """Ask an application for its version; failure yields ``unknown`` rather than an error.

    Returns
    -------
    ToolIdentity
        The reported version number, or ``unknown`` when it cannot be determined.

    """
    try:
        completed = run_bounded([executable, *version_args], timeout=IDENTIFY_TIMEOUT_SECONDS)
    except OSError, subprocess.TimeoutExpired:
        return ToolIdentity(name, "unknown")
    found = VERSION_RE.search(completed.stdout or completed.stderr)
    return ToolIdentity(name, found.group(0) if found else "unknown")
