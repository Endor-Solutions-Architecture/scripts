"""Parsing for the Endor webhook envelope defined in spec section 7.

Almost every field is optional with a default: the Go templates guard nil
protobuf wrappers with `with`, which omits the guarded body, so an absent
AggregationDetails or Diff arrives as an empty JSON object. Only the
notification uuid and project uuid are genuinely required -- the uuid is the
correlation key and the project uuid is the parent grouping key.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

NO_DEPS_SENTINEL = "__ENDOR_FINDINGS_WITH_NO_DEPS__"


class EnvelopeError(Exception):
    """Raised when a request body is not a usable Endor webhook envelope."""


class Finding(BaseModel):
    uuid: str
    description: str = ""
    severity: str = ""
    dependency: str | None = None
    package: str | None = None
    finding_url: str | None = None


class Aggregation(BaseModel):
    type: str = ""
    target_name: str = ""
    pkg_version_uuid: str = ""


class NotificationBlock(BaseModel):
    uuid: str
    project_uuid: str
    project_name: str = ""
    project_app_url: str = ""
    ref_name: str = ""
    context_id: str = ""
    policy_uuid: str = ""
    policy_name: str = ""
    policy_app_url: str = ""
    aggregation: Aggregation = Field(default_factory=Aggregation)


class Diff(BaseModel):
    new_finding_uuids: list[str] = Field(default_factory=list)
    resolved_finding_uuids: list[str] = Field(default_factory=list)


class Envelope(BaseModel):
    event: Literal["open", "update", "resolve"]
    notification: NotificationBlock
    diff: Diff = Field(default_factory=Diff)
    findings: list[Finding] = Field(default_factory=list)


def parse_envelope(raw_body: bytes) -> Envelope:
    """Parse and validate a webhook body, raising EnvelopeError on any problem."""
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EnvelopeError(f"request body is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise EnvelopeError("request body must be a JSON object")

    try:
        return Envelope.model_validate(payload)
    except ValidationError as exc:
        raise EnvelopeError(f"invalid webhook envelope: {exc}") from exc
