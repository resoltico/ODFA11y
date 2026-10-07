# SPDX-License-Identifier: MPL-2.0
"""Names for temporary files and directories published by atomic rename.

Unlike ``tempfile.mkstemp`` and ``mkdtemp``, which create owner-only entries, these
names let the caller create the entry with the process's normal permissions (umask), so a
published output is as readable as any other file the user creates.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def staging_sibling(destination: Path) -> Path:
    """Choose an unused hidden name in the destination's directory.

    Returns
    -------
    Path
        A path that does not exist yet and shares the destination's directory, so renaming
        it onto the destination stays on one file system.

    """
    return destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
