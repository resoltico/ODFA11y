# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for capability probes."""

lazy from collections.abc import Callable

import pytest

from odfa11y.families.probes import CapabilityStatus, ProbeId, measure_probe
from odfa11y.native.libreoffice import find_soffice, identify_soffice
from tests.families.test_capability_probes import PROBES
from tests.fixtures.native import export_settings, validator_tool


@pytest.mark.parametrize("probe_id", list(ProbeId))
def test_each_native_probe_produces_a_scoped_observation(
    probe_id: ProbeId, external_tool: Callable[..., str]
) -> None:
    validator = (
        validator_tool(external_tool("verapdf")) if PROBES[probe_id].requires_validator else None
    )
    executable = find_soffice(external_tool("soffice", "libreoffice"))
    identity = identify_soffice(executable)
    execution = measure_probe(
        PROBES[probe_id],
        identity,
        export_settings(PROBES[probe_id].export_filter, executable),
        verapdf=validator,
    )
    assert execution.error is None, execution.error
    assert execution.result.status in {CapabilityStatus.SUPPORTED, CapabilityStatus.UNSUPPORTED}
    assert execution.result.id == probe_id
    assert execution.result.family == PROBES[probe_id].family
    assert execution.result.tool == identity
