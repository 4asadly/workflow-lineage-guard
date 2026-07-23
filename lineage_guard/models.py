"""Dependency-light data contracts used by the engine and API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ChangeKind = Literal["renamed", "removed", "retyped", "added"]
Verdict = Literal["safe", "needs_review", "blocked"]


@dataclass(slots=True)
class SchemaChange:
    kind: ChangeKind
    field: str
    replacement: str | None = None
    old_type: str | None = None
    new_type: str | None = None
    confidence: float = 1.0


@dataclass(slots=True)
class ReferenceHit:
    field: str
    json_pointer: str
    node_name: str | None
    value_preview: str


@dataclass(slots=True)
class PatchRecord:
    json_pointer: str
    node_name: str | None
    old_field: str
    new_field: str
    before: str
    after: str


@dataclass(slots=True)
class Finding:
    severity: Literal["info", "warning", "critical"]
    title: str
    explanation: str
    field: str
    replacement: str | None
    references: list[ReferenceHit] = field(default_factory=list)
    auto_fixable: bool = False


@dataclass(slots=True)
class ValidationReport:
    workflow_name: str
    dataset_urn: str
    verdict: Verdict
    risk_score: int
    summary: str
    schema_changes: list[SchemaChange]
    findings: list[Finding]
    patches: list[PatchRecord]
    fixed_workflow: dict[str, Any]
    writeback_markdown: str
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
