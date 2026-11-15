# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for capability probes."""

lazy from collections.abc import Callable

import pytest

from odfa11y.native.export import ExportSettings, find_soffice, identify_soffice
from odfa11y.native.probes import CapabilityStatus, ProbeCache, ProbeId
from tests.families.test_capability_probes import PROBES


@pytest.mark.parametrize("probe_id", list(ProbeId))
def test_each_native_probe_produces_a_scoped_observation(
    probe_id: ProbeId, external_tool: Callable[..., str]
) -> None:
    executable = find_soffice(external_tool("soffice", "libreoffice"))
    identity = identify_soffice(executable)
    execution = ProbeCache().run(
        PROBES[probe_id],
        identity,
        ExportSettings(PROBES[probe_id].export_filter, executable),
        verapdf_path=external_tool("verapdf"),
    )
    assert execution.error is None, execution.error
    assert execution.result.status in {CapabilityStatus.SUPPORTED, CapabilityStatus.UNSUPPORTED}
    assert execution.result.id == probe_id
    assert execution.result.family == PROBES[probe_id].family
    assert execution.result.tool == identity
