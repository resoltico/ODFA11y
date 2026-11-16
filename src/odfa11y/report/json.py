# SPDX-License-Identifier: AGPL-3.0-only
"""Serialize typed contracts as JSON without presentation policy."""

import json

from odfa11y.contracts import encode


def render_json(value: object) -> str:
    """Render a result or report using its authoritative contract."""
    return json.dumps(encode(value), indent=2, ensure_ascii=False, sort_keys=True)
