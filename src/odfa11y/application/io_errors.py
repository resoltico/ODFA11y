# SPDX-License-Identifier: AGPL-3.0-only
"""Translate filesystem exceptions at application boundaries."""

from collections.abc import Callable
from functools import wraps

from odfa11y.errors import IoFailure


def translate_io[**P, R](operation: Callable[P, R]) -> Callable[P, R]:
    """Wrap expected filesystem failures without swallowing programming errors."""

    @wraps(operation)
    def invoke(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return operation(*args, **kwargs)
        except OSError as error:
            raise IoFailure.from_oserror(error) from error

    return invoke
