# SPDX-License-Identifier: MPL-2.0
"""The one required check: the ruleset, the gate job and the jobs it waits for must agree."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8")
RULESET = json.loads((ROOT / ".github/rulesets/default-branch.json").read_text(encoding="utf-8"))
GITHUB_ACTIONS_APP_ID = 15368


def job_block(job_id: str) -> str:
    """Return the text of a top-level workflow job.

    Returns
    -------
    str
        The job's lines up to the next top-level job.

    """
    match = re.search(rf"^  {re.escape(job_id)}:\n((?:    .*\n|\n)+)", WORKFLOW, re.MULTILINE)
    assert match, f"job {job_id} not found"
    return match.group(1)


def job_ids() -> list[str]:
    """List the workflow's top-level job ids.

    Returns
    -------
    list[str]
        Job ids in file order.

    """
    jobs = WORKFLOW.split("\njobs:\n", 1)[1]
    return re.findall(r"^  ([a-z][a-z0-9-]*):\n", jobs, re.MULTILINE)


def test_the_ruleset_requires_exactly_the_gate_job_by_its_display_name() -> None:
    gate_name = re.search(r"^    name: (.+)$", job_block("ci-gate"), re.MULTILINE)
    assert gate_name
    checks = next(
        rule["parameters"]["required_status_checks"]
        for rule in RULESET["rules"]
        if rule["type"] == "required_status_checks"
    )
    assert checks == [{"context": gate_name.group(1), "integration_id": GITHUB_ACTIONS_APP_ID}]


def test_the_gate_always_runs_and_waits_for_every_other_non_release_job() -> None:
    block = job_block("ci-gate")
    assert "if: always()" in block
    needed = re.search(r"needs: \[(.+)\]", block)
    assert needed
    waited = {name.strip() for name in needed.group(1).split(",")}
    assert waited == set(job_ids()) - {"ci-gate", "draft"}


def test_the_release_job_depends_on_the_gate_alone() -> None:
    assert re.search(r"needs: \[ci-gate\]", job_block("draft"))


def test_a_draft_release_is_created_only_by_a_manual_run_on_main() -> None:
    block = job_block("draft")
    assert (
        "if: github.event_name == 'workflow_dispatch' && inputs.release"
        " && github.ref == 'refs/heads/main'" in block
    )
    assert "environment: release" in block
    assert "--target" in block
    assert "--verify-tag" not in block
    assert "refs/tags" not in block


def test_the_gate_demands_success_not_merely_absence_of_failure() -> None:
    assert '.result == "success"' in job_block("ci-gate")


def test_the_ruleset_blocks_deletion_and_history_rewrites() -> None:
    assert {rule["type"] for rule in RULESET["rules"]} >= {"deletion", "non_fast_forward"}


def test_check_triggers_cover_prs_main_tags_and_manual_branch_runs() -> None:
    triggers = WORKFLOW.split("\nenv:", 1)[0]
    assert '  push:\n    branches: [main]\n    tags: ["v*"]\n' in triggers
    assert "  pull_request:\n" in triggers
    assert "  workflow_dispatch:\n" in triggers
    assert "paths:" not in triggers
    assert "paths-ignore:" not in triggers
    # These jobs also run on manually selected branches; only release creation is restricted.
    for job in ("static", "test", "integration"):
        assert not re.search(r"^    if:", job_block(job), re.MULTILINE)


def test_tag_and_manual_release_runs_cannot_restore_go_analysis_caches() -> None:
    cache = re.search(
        r"- name: Cache pinned Go analysis tools\n((?: {8}.*\n)+)",
        WORKFLOW,
    )
    assert cache is not None
    block = cache.group(1)
    assert "if: github.event_name != 'workflow_dispatch' || !inputs.release" in block
    assert "lookup-only: ${{ startsWith(github.ref, 'refs/tags/') }}" in block


def test_parallel_native_tests_still_require_tools_and_reject_worker_crashes() -> None:
    integration = job_block("integration")
    assert 'ODFA11Y_REQUIRE_INTEGRATION: "1"' in integration
    assert "pytest -m integration -n 2 --max-worker-restart=0" in integration
    assert "os: [ubuntu-latest, macos-latest, windows-latest]" in integration
