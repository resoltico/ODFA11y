# SPDX-License-Identifier: MPL-2.0
"""Generate published reference artifacts from their typed authorities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from odfa11y.adapter import Outcome, ReviewItem, Status
from odfa11y.batch.record import BatchItemResult, BatchRecord
from odfa11y.external_tools import ToolIdentity
from odfa11y.fidelity import FidelityPolicy
from odfa11y.outcomes import BatchStatus, ExitStatus, ReviewTopic, RunStatus, StageName, StageStatus
from odfa11y.pipeline import Profile, RunRecord, StageResult
from odfa11y.records import DoctorRecord, DocumentIdentity, SchemaCheck, Toolchain
from odfa11y.remediation import RemediationResult
from odfa11y.report import FACT_REGISTRY, FactSet, Finding, Location, Report
from odfa11y.serialization import JsonObject, JsonValue, schema_for

SCHEMA_DIRECTORY = Path(__file__).resolve().parents[1] / "src/odfa11y/schemas"
FORMATS = {
    "report": Report,
    "run": RunRecord,
    "batch": BatchRecord,
    "doctor": DoctorRecord,
    "remediation": RemediationResult,
}
# Supply type-only names while resolving record annotations; runtime modules stay layered.
TYPE_NAMESPACE = {
    value.__name__: value
    for value in (
        Outcome,
        ReviewItem,
        Status,
        BatchItemResult,
        BatchRecord,
        ToolIdentity,
        FidelityPolicy,
        BatchStatus,
        ExitStatus,
        ReviewTopic,
        RunStatus,
        StageName,
        StageStatus,
        Profile,
        RunRecord,
        StageResult,
        DoctorRecord,
        DocumentIdentity,
        SchemaCheck,
        Toolchain,
        RemediationResult,
        FactSet,
        Finding,
        Location,
        Report,
    )
} | {"JsonObject": JsonObject, "JsonValue": JsonValue, "Path": Path}


def schemas() -> dict[str, JsonObject]:
    """Derive all versioned JSON format schemas from registered record types.

    Returns
    -------
    dict[str, JsonObject]
        Generated schemas keyed by their public format names.

    """
    fact_properties: JsonObject = {
        key.id: schema_for(key.value_type, namespace=TYPE_NAMESPACE)
        | {"description": key.description}
        for key in FACT_REGISTRY.values()
    }
    overrides: dict[object, JsonObject] = {
        FactSet: {"type": "object", "properties": fact_properties, "additionalProperties": False},
    }
    result = {
        name: {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"urn:odfa11y:schema:{name}",
            **schema_for(record_type, namespace=TYPE_NAMESPACE, overrides=overrides),
        }
        for name, record_type in FORMATS.items()
    }
    result["plan"] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:odfa11y:schema:plan",
        "$comment": "Reserved for the decision codec in WP-06; not an accepted plan contract.",
        "not": {},
    }
    return result


def main() -> int:
    """Write reference artifacts or fail when the committed copies are stale.

    Returns
    -------
    int
        Zero for current/generated references; one for stale check-mode outputs.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail instead of updating stale files."
    )
    args = parser.parse_args()
    stale = []
    for name, schema in schemas().items():
        path = SCHEMA_DIRECTORY / f"{name}.schema.json"
        expected = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != expected:
                stale.append(str(path))
        else:
            path.write_text(expected, encoding="utf-8")
    if stale:
        parser.exit(1, "Stale generated references:\n" + "\n".join(stale) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
