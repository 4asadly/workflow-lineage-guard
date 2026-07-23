"""Deterministic schema-impact and safe n8n workflow repair engine."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterator, Mapping
from difflib import SequenceMatcher
from typing import Any

from .models import (
    Finding,
    PatchRecord,
    ReferenceHit,
    SchemaChange,
    ValidationReport,
)

# Covers the common n8n forms: $json.email, $json["email"],
# $node["Fetch"].json.email, item.json.email, body.email, and input.email.
REFERENCE_PATTERNS = (
    re.compile(r"\$json\.([A-Za-z_][\w-]*)"),
    re.compile(r"\$json\[['\"]([^'\"]+)['\"]\]"),
    re.compile(r"\.json\.([A-Za-z_][\w-]*)"),
    re.compile(r"\b(?:item\.json|body|input|data)\.([A-Za-z_][\w-]*)"),
)


def _escape_pointer(part: str) -> str:
    return part.replace("~", "~0").replace("/", "~1")


def _walk(value: Any, pointer: str = "") -> Iterator[tuple[str, Any, str | None]]:
    """Yield every JSON value with its pointer and closest n8n node name."""
    if isinstance(value, dict):
        node_name = value.get("name") if isinstance(value.get("name"), str) else None
        for key, child in value.items():
            child_pointer = f"{pointer}/{_escape_pointer(str(key))}"
            if node_name and isinstance(child, (str, int, float, bool, type(None))):
                yield child_pointer, child, node_name
            else:
                for item_pointer, item, inherited_name in _walk(child, child_pointer):
                    yield item_pointer, item, inherited_name or node_name
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{pointer}/{index}")
    else:
        yield pointer or "/", value, None


def _referenced_fields(text: str) -> set[str]:
    fields: set[str] = set()
    for pattern in REFERENCE_PATTERNS:
        fields.update(match.group(1) for match in pattern.finditer(text))
    return fields


def extract_references(workflow: Mapping[str, Any]) -> dict[str, list[ReferenceHit]]:
    """Extract field references with exact evidence locations."""
    references: dict[str, list[ReferenceHit]] = {}
    for pointer, value, node_name in _walk(workflow):
        if not isinstance(value, str):
            continue
        fields = _referenced_fields(value)
        # Exact bare values are common in Set/Map nodes.
        if re.fullmatch(r"[A-Za-z_][\w-]*", value):
            fields.add(value)
        for field in fields:
            references.setdefault(field, []).append(
                ReferenceHit(
                    field=field,
                    json_pointer=pointer,
                    node_name=node_name,
                    value_preview=value[:180],
                )
            )
    return references


def _normalize_schema(schema: Mapping[str, Any] | list[dict[str, Any]]) -> dict[str, str]:
    if isinstance(schema, Mapping):
        return {str(name): str(field_type) for name, field_type in schema.items()}
    normalized: dict[str, str] = {}
    for field in schema:
        name = field.get("name") or field.get("fieldPath")
        if name:
            normalized[str(name)] = str(
                field.get("type") or field.get("nativeDataType") or "unknown"
            )
    return normalized


def diff_schemas(
    current_schema: Mapping[str, Any] | list[dict[str, Any]],
    proposed_schema: Mapping[str, Any] | list[dict[str, Any]],
    rename_map: Mapping[str, str] | None = None,
) -> list[SchemaChange]:
    """Return explicit and conservative inferred schema changes."""
    current = _normalize_schema(current_schema)
    proposed = _normalize_schema(proposed_schema)
    rename_map = dict(rename_map or {})
    removed = set(current) - set(proposed)
    added = set(proposed) - set(current)
    changes: list[SchemaChange] = []

    for old, new in rename_map.items():
        if old in removed and new in added:
            changes.append(
                SchemaChange(
                    kind="renamed",
                    field=old,
                    replacement=new,
                    old_type=current[old],
                    new_type=proposed[new],
                    confidence=1.0,
                )
            )
            removed.remove(old)
            added.remove(new)

    # Infer only an unambiguous, type-compatible, reasonably similar rename.
    candidates: list[tuple[float, str, str]] = []
    for old in removed:
        for new in added:
            if current[old].lower() == proposed[new].lower():
                score = SequenceMatcher(None, old.lower(), new.lower()).ratio()
                if score >= 0.45:
                    candidates.append((score, old, new))
    candidates.sort(reverse=True)
    used_old: set[str] = set()
    used_new: set[str] = set()
    for score, old, new in candidates:
        if old in used_old or new in used_new:
            continue
        old_options = [candidate for candidate in candidates if candidate[1] == old]
        new_options = [candidate for candidate in candidates if candidate[2] == new]
        if len(old_options) == 1 and len(new_options) == 1:
            changes.append(
                SchemaChange(
                    kind="renamed",
                    field=old,
                    replacement=new,
                    old_type=current[old],
                    new_type=proposed[new],
                    confidence=round(score, 2),
                )
            )
            used_old.add(old)
            used_new.add(new)

    removed -= used_old
    added -= used_new
    changes.extend(
        SchemaChange(kind="removed", field=name, old_type=current[name]) for name in sorted(removed)
    )
    changes.extend(
        SchemaChange(kind="added", field=name, new_type=proposed[name]) for name in sorted(added)
    )
    for name in sorted(set(current) & set(proposed)):
        if current[name].lower() != proposed[name].lower():
            changes.append(
                SchemaChange(
                    kind="retyped",
                    field=name,
                    old_type=current[name],
                    new_type=proposed[name],
                )
            )
    return changes


def _replace_field(text: str, old: str, new: str) -> str:
    escaped = re.escape(old)
    substitutions = (
        (rf"(?<=\$json\.){escaped}\b", new),
        (rf"(?<=\.json\.){escaped}\b", new),
        (rf"(?<=body\.){escaped}\b", new),
        (rf"(?<=input\.){escaped}\b", new),
        (rf"(?<=data\.){escaped}\b", new),
        (rf"(?<=\['){escaped}(?='\])", new),
        (rf'(?<=\["){escaped}(?="\])', new),
    )
    result = text
    for pattern, replacement in substitutions:
        result = re.sub(pattern, replacement, result)
    if result == text and text == old:
        return new
    return result


def _patch_workflow(
    value: Any, renames: Mapping[str, str], pointer: str = "", node: str | None = None
):
    patches: list[PatchRecord] = []
    if isinstance(value, dict):
        current_node = value.get("name") if isinstance(value.get("name"), str) else node
        patched: dict[str, Any] = {}
        for key, child in value.items():
            child_value, child_patches = _patch_workflow(
                child,
                renames,
                f"{pointer}/{_escape_pointer(str(key))}",
                current_node,
            )
            patched[key] = child_value
            patches.extend(child_patches)
        return patched, patches
    if isinstance(value, list):
        patched_list = []
        for index, child in enumerate(value):
            child_value, child_patches = _patch_workflow(child, renames, f"{pointer}/{index}", node)
            patched_list.append(child_value)
            patches.extend(child_patches)
        return patched_list, patches
    if isinstance(value, str):
        result = value
        for old, new in renames.items():
            updated = _replace_field(result, old, new)
            if updated != result:
                patches.append(
                    PatchRecord(
                        json_pointer=pointer or "/",
                        node_name=node,
                        old_field=old,
                        new_field=new,
                        before=result,
                        after=updated,
                    )
                )
                result = updated
        return result, patches
    return value, patches


def _writeback_markdown(
    workflow_name: str,
    dataset_urn: str,
    verdict: str,
    risk_score: int,
    findings: list[Finding],
    patches: list[PatchRecord],
) -> str:
    lines = [
        "## Workflow Lineage Guard",
        "",
        f"**Workflow:** `{workflow_name}`  ",
        f"**Dataset:** `{dataset_urn}`  ",
        f"**Verdict:** **{verdict.replace('_', ' ').upper()}** (risk {risk_score}/100)",
        "",
        "### Impact evidence",
    ]
    if findings:
        for finding in findings:
            nodes = sorted({hit.node_name or "unnamed node" for hit in finding.references})
            lines.append(
                f"- **{finding.field}** — {finding.explanation} Nodes: {', '.join(nodes)}."
            )
    else:
        lines.append("- No referenced breaking schema changes were found.")
    lines.extend(["", "### Automated action"])
    if patches:
        for patch in patches:
            lines.append(
                f"- `{patch.node_name or patch.json_pointer}`: "
                f"`{patch.old_field}` → `{patch.new_field}`"
            )
    else:
        lines.append("- No automatic patch was applied.")
    lines.extend(
        [
            "",
            "> Generated from schema evidence and exact workflow JSON references. "
            "Review before deployment.",
        ]
    )
    return "\n".join(lines)


def analyze_workflow(
    workflow: Mapping[str, Any],
    current_schema: Mapping[str, Any] | list[dict[str, Any]],
    proposed_schema: Mapping[str, Any] | list[dict[str, Any]],
    *,
    dataset_urn: str = "urn:li:dataset:(urn:li:dataPlatform:demo,customers,PROD)",
    rename_map: Mapping[str, str] | None = None,
    lineage_path: list[str] | None = None,
) -> ValidationReport:
    """Analyze one workflow and return evidence, a safe patch, and DataHub write-back text."""
    workflow_copy = copy.deepcopy(dict(workflow))
    workflow_name = str(workflow.get("name") or "Unnamed workflow")
    changes = diff_schemas(current_schema, proposed_schema, rename_map)
    references = extract_references(workflow)
    findings: list[Finding] = []

    renames: dict[str, str] = {}
    for change in changes:
        hits = references.get(change.field, [])
        if not hits or change.kind == "added":
            continue
        if change.kind == "renamed" and change.replacement:
            renames[change.field] = change.replacement
            findings.append(
                Finding(
                    severity="critical",
                    title=f"Referenced field renamed: {change.field}",
                    explanation=(
                        f"{len(hits)} exact workflow reference(s) must move to "
                        f"{change.replacement}."
                    ),
                    field=change.field,
                    replacement=change.replacement,
                    references=hits,
                    auto_fixable=True,
                )
            )
        elif change.kind == "removed":
            findings.append(
                Finding(
                    severity="critical",
                    title=f"Referenced field removed: {change.field}",
                    explanation=f"{len(hits)} workflow reference(s) have no verified replacement.",
                    field=change.field,
                    replacement=None,
                    references=hits,
                    auto_fixable=False,
                )
            )
        elif change.kind == "retyped":
            findings.append(
                Finding(
                    severity="warning",
                    title=f"Referenced field changed type: {change.field}",
                    explanation=(
                        f"Type changed from {change.old_type} to {change.new_type}; "
                        "runtime behavior may differ."
                    ),
                    field=change.field,
                    replacement=None,
                    references=hits,
                    auto_fixable=False,
                )
            )

    fixed_workflow, patches = _patch_workflow(workflow_copy, renames)
    unresolved_critical = any(
        finding.severity == "critical" and not finding.auto_fixable for finding in findings
    )
    warnings = any(finding.severity == "warning" for finding in findings)
    if unresolved_critical:
        verdict = "blocked"
    elif findings or warnings:
        verdict = "needs_review"
    else:
        verdict = "safe"

    risk_score = min(
        100,
        sum(
            (45 if finding.severity == "critical" else 20) + min(15, len(finding.references) * 3)
            for finding in findings
        ),
    )
    if not findings:
        risk_score = 0
    summary = {
        "safe": "No referenced breaking change was detected.",
        "needs_review": (
            f"Detected {len(findings)} impact(s); generated {len(patches)} safe patch(es)."
        ),
        "blocked": "A breaking change has no verified automatic fix. Deployment should stop.",
    }[verdict]
    writeback = _writeback_markdown(
        workflow_name, dataset_urn, verdict, risk_score, findings, patches
    )
    return ValidationReport(
        workflow_name=workflow_name,
        dataset_urn=dataset_urn,
        verdict=verdict,
        risk_score=risk_score,
        summary=summary,
        schema_changes=changes,
        findings=findings,
        patches=patches,
        fixed_workflow=fixed_workflow,
        writeback_markdown=writeback,
        provenance={
            "source": "request payload" if lineage_path else "local demo fixture",
            "datahub_verified": False,
            "datahub_tool_calls": [],
            "lineage_path": lineage_path or [],
            "workflow_sha256": __import__("hashlib")
            .sha256(json.dumps(workflow, sort_keys=True).encode())
            .hexdigest(),
            "method": "deterministic schema diff + exact JSON reference scan",
        },
    )
