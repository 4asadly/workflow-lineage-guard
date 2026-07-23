"""Helpers for producing credential-safe evidence from a real DataHub MCP server."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit


def jsonable(value: Any) -> Any:
    """Convert MCP/Pydantic results into values that can be written as JSON."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def safe_endpoint(url: str) -> str:
    """Return only the public scheme, host, and path—never credentials or query values."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme}://{host}{parsed.path}"


def parse_embedded_json(value: Any) -> Any:
    """Parse JSON strings embedded in MCP text content while preserving ordinary strings."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return parse_embedded_json(json.loads(stripped))
            except json.JSONDecodeError:
                return value
        return value
    if isinstance(value, Mapping):
        return {key: parse_embedded_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [parse_embedded_json(item) for item in value]
    return value


def find_dataset_urn(value: Any) -> str | None:
    """Return the first dataset URN found in an MCP result."""
    parsed = parse_embedded_json(jsonable(value))
    stack = [parsed]
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            if current.startswith("urn:li:dataset:"):
                return current
            continue
        if isinstance(current, Mapping):
            preferred = [
                current.get("urn"),
                current.get("entityUrn"),
                current.get("entity_urn"),
            ]
            for candidate in preferred:
                if isinstance(candidate, str) and candidate.startswith("urn:li:dataset:"):
                    return candidate
            stack.extend(reversed(list(current.values())))
        elif isinstance(current, list):
            stack.extend(reversed(current))
    return None


def tool_schema(tool: Any) -> dict[str, Any]:
    """Extract a tool's JSON input schema across MCP SDK naming conventions."""
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = getattr(tool, "input_schema", None)
    return jsonable(schema or {})


def build_update_description_payload(
    schema: Mapping[str, Any],
    *,
    dataset_urn: str,
    description: str,
) -> dict[str, Any]:
    """Build the official DataHub update_description payload from its advertised schema."""
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        properties = {}

    urn_key = next(
        (key for key in ("entity_urn", "entityUrn", "urn") if key in properties),
        "entity_urn",
    )
    description_key = next(
        (key for key in ("description", "text", "value") if key in properties),
        "description",
    )
    payload: dict[str, Any] = {
        urn_key: dataset_urn,
        description_key: description,
    }
    if "operation" in properties:
        payload["operation"] = "append"
    return payload


def evidence_marker(now: datetime | None = None) -> str:
    """Create a visible, timestamped proof marker for a controlled DataHub write-back."""
    timestamp = (now or datetime.now(UTC)).isoformat()
    return (
        "\n\n---\n"
        "### Workflow Lineage Guard — live MCP verification\n\n"
        f"Verified direct DataHub MCP read/write access at `{timestamp}`. "
        "This marker was appended only after an explicit write-back approval."
    )
