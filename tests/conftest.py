# SPDX-License-Identifier: MPL-2.0
"""Configure Hypothesis for deterministic, bounded runs."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck, settings
from jsonschema import Draft202012Validator

from odfa11y.schemas import read_schema
from tools.generate_reference import FORMATS

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from jsonschema.protocols import Validator

    from odfa11y.serialization import JsonObject

RECORD_VALIDATORS = {
    record_type: Draft202012Validator(read_schema(name)) for name, record_type in FORMATS.items()
}

settings.register_profile(
    "default",
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile("smoke", parent=settings.get_profile("default"), max_examples=5)
settings.load_profile("default")


@pytest.fixture
def external_tool() -> Callable[..., str]:
    """Locate an external application, skipping locally but failing where it is required.

    Returns
    -------
    Callable[..., str]
        A locator returning the first executable found among the given names.

    """

    def locate(*names: str) -> str:
        for name in names:
            if found := shutil.which(name):
                return found
        message = f"{names[0]} is not installed"
        if os.environ.get("ODFA11Y_REQUIRE_INTEGRATION"):
            pytest.fail(message)
        pytest.skip(message)

    return locate


@pytest.fixture(autouse=True)  # ruff: ignore[pytest-fixture-autouse]  Validate every emitted record.
def validate_published_record_shapes() -> Iterator[None]:
    """Validate every root record without changing test fixture cleanup ordering.

    Yields
    ------
    None
        The test runs while serializers validate their packaged contracts.

    """
    with pytest.MonkeyPatch.context() as shape_patch:
        for record_type, validator in RECORD_VALIDATORS.items():
            shape_patch.setattr(
                record_type, "as_dict", _validated_serializer(record_type.as_dict, validator)
            )
        yield


def _validated_serializer[T](
    original: Callable[[T], JsonObject], validator: Validator
) -> Callable[[T], JsonObject]:
    def checked(value: T) -> JsonObject:
        result = original(value)
        validator.validate(result)
        return result

    return checked
