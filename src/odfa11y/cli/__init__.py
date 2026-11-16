# SPDX-License-Identifier: MPL-2.0
"""The command-line boundary owns process-level interruption policy."""

import signal
import threading

from odfa11y import NativeTools

from .commands import main as run_command


def _interrupt(_number, _frame) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None, *, native_tools: NativeTools | None = None) -> int:
    if threading.current_thread() is not threading.main_thread():
        return run_command(argv, native_tools=native_tools)
    previous = signal.signal(signal.SIGTERM, _interrupt)
    try:
        return run_command(argv, native_tools=native_tools)
    finally:
        signal.signal(signal.SIGTERM, previous)


__all__ = ["main"]
