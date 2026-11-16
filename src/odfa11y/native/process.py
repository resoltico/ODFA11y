# SPDX-License-Identifier: MPL-2.0
"""Locate and identify the external applications ODFA11y drives."""

import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from odfa11y.errors import Remedy, RemedyAction, ToolUnavailable
from odfa11y.tool_identity import ToolIdentity
from odfa11y.tool_timeout import Timeout

MAX_OUTPUT_BYTES = 64 * 1024
READ_CHUNK_BYTES = 64 * 1024
READER_JOIN_SECONDS = 3
VERSION_RE = re.compile(r"\d+(?:\.\d+)+")

# Windows reserves 0xffffffff milliseconds for an infinite wait.


@dataclass(frozen=True, slots=True)
class ToolRun:
    """A finished external process: its status and the head of each output stream."""

    returncode: int
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool

    @property
    def truncated(self) -> bool:
        """Whether either stream was cut at the limit."""
        return self.stdout_truncated or self.stderr_truncated


def run_bounded(
    command: list[str], *, timeout: float, max_output: int = MAX_OUTPUT_BYTES
) -> ToolRun:
    """Run a program with a time limit and bounded output capture.

    Capture each stream's first ``max_output`` bytes; drain and discard the rest. Timeout
    or interruption kills the process tree where supported; ``subprocess.TimeoutExpired``
    propagates after cleanup. Descendants holding pipes open get bounded cleanup grace,
    then termination; descendants that escape the process group may remain running.

    Returns
    -------
    ToolRun
        The exit status and the captured heads of stdout and stderr.
    """
    timeout = Timeout(timeout)
    process = subprocess.Popen(  # noqa: S603  Arguments select a local tool without a shell.
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    captured = [_Capture(process.stdout, max_output), _Capture(process.stderr, max_output)]
    threads = [threading.Thread(target=capture.drain, daemon=True) for capture in captured]
    for thread in threads:
        thread.start()
    try:
        process.wait(timeout=timeout)
    except BaseException:
        _kill_tree(process)
        process.wait()
        _join(threads)
        raise
    if not _join(threads):
        _kill_tree(process)  # a descendant still holds the pipes open
        _join(threads)
    return ToolRun(
        process.returncode,
        captured[0].text(),
        captured[1].text(),
        captured[0].truncated,
        captured[1].truncated,
    )


def _join(threads: list[threading.Thread]) -> bool:
    deadline = time.monotonic() + READER_JOIN_SECONDS
    for thread in threads:
        thread.join(max(deadline - time.monotonic(), 0))
    return not any(thread.is_alive() for thread in threads)


class _Capture:
    def __init__(self, stream: IO[bytes] | None, limit: int) -> None:
        self._stream = stream
        self._limit = limit
        self._head = bytearray()
        self.truncated = False

    def drain(self) -> None:
        stream = self._stream
        if stream is None:
            return
        try:
            while chunk := stream.read(READ_CHUNK_BYTES):
                room = self._limit - len(self._head)
                self._head += chunk[: max(room, 0)]
                self.truncated = self.truncated or len(chunk) > room
        except OSError, ValueError:
            return  # the pipe broke under us
        finally:
            stream.close()

    def text(self) -> str:
        return self._head.decode("utf-8", errors="replace")


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(  # noqa: S603  Arguments select a local tool without a shell.
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],  # noqa: S607  System tool is resolved through PATH.
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
    process.kill()


def find_executable(requested: str | Path | None, candidates: tuple[str, ...]) -> str:
    """Resolve an explicit path or program name, or search the candidate names on PATH.

    Returns
    -------
    str
        The executable's path.

    Raises
    ------
    ToolUnavailable
        The requested executable, or every candidate, cannot be found.
    """
    if requested is not None:
        path = Path(requested)
        if path.is_file():
            if not os.access(path, os.X_OK):
                msg = f"Not executable: {requested}"
                raise ToolUnavailable(msg, remedy=Remedy(RemedyAction.INSTALL_TOOL, candidates[0]))
            return str(path)
        resolved = shutil.which(str(requested))
        if resolved:
            return resolved
        msg = f"Executable not found: {requested}"
        raise ToolUnavailable(msg, remedy=Remedy(RemedyAction.INSTALL_TOOL, candidates[0]))
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    msg = f"None of {', '.join(candidates)} was found on PATH."
    raise ToolUnavailable(msg, remedy=Remedy(RemedyAction.INSTALL_TOOL, candidates[0]))


def identify(
    name: str,
    executable: str,
    version_args: tuple[str, ...],
    *,
    timeout: float = Timeout.DEFAULT,
    runner: Callable[..., ToolRun] = run_bounded,
) -> ToolIdentity:
    """Ask an application for its version; failure yields ``unknown`` rather than an error.

    Returns
    -------
    ToolIdentity
        The reported version number, or ``unknown`` when it cannot be determined.
    """
    try:
        completed = runner([executable, *version_args], timeout=Timeout(timeout))
    except OSError, subprocess.TimeoutExpired:
        return ToolIdentity(name, "unknown")
    found = VERSION_RE.search(completed.stdout or completed.stderr)
    return ToolIdentity(name, found.group(0) if found else "unknown")


def identify_by_file_version(
    name: str,
    executable: str,
    *,
    timeout: float = Timeout.DEFAULT,
    runner: Callable[..., ToolRun] = run_bounded,
) -> ToolIdentity:
    """Read an executable's product version from its file metadata, without running it.

    LibreOffice's Windows ``--version`` starts a session without returning.

    Returns
    -------
    ToolIdentity
        The product version, or ``unknown`` when it cannot be read.
    """
    quoted = executable.replace("'", "''")
    script = f"(Get-Item -LiteralPath '{quoted}').VersionInfo.ProductVersion"
    command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    try:
        completed = runner(command, timeout=Timeout(timeout))
    except OSError, subprocess.TimeoutExpired:
        return ToolIdentity(name, "unknown")
    found = VERSION_RE.search(completed.stdout)
    return ToolIdentity(name, found.group(0) if found else "unknown")


def identify_running_or_by_file(
    name: str,
    executable: str,
    version_args: tuple[str, ...],
    *,
    runner: Callable[..., ToolRun] = run_bounded,
    timeout: float = Timeout.DEFAULT,
) -> ToolIdentity:
    """Identify via runtime version, or Windows file metadata.

    Returns
    -------
    ToolIdentity
        The reported version, or ``unknown`` on failure.
    """
    if sys.platform == "win32":
        return identify_by_file_version(name, executable, runner=runner, timeout=timeout)
    return identify(name, executable, version_args, timeout=timeout, runner=runner)
