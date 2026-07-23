from __future__ import annotations

from datetime import UTC, datetime

from lineage_guard.live_evidence import (
    build_update_description_payload,
    evidence_marker,
    find_dataset_urn,
    safe_endpoint,
)


def test_find_dataset_urn_inside_mcp_text_content() -> None:
    urn = "urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.customers,PROD)"
    result = {"content": [{"type": "text", "text": f'{{"entity": {{"urn": "{urn}"}}}}'}]}

    assert find_dataset_urn(result) == urn


def test_build_official_update_description_payload() -> None:
    schema = {
        "type": "object",
        "properties": {
            "entity_urn": {"type": "string"},
            "operation": {"enum": ["replace", "append", "remove"]},
            "description": {"type": ["string", "null"]},
            "column_path": {"type": ["string", "null"]},
        },
    }

    assert build_update_description_payload(
        schema,
        dataset_urn="urn:li:dataset:test",
        description="proof",
    ) == {
        "entity_urn": "urn:li:dataset:test",
        "operation": "append",
        "description": "proof",
    }


def test_safe_endpoint_strips_credentials_and_query() -> None:
    assert (
        safe_endpoint("https://user:secret@example.acryl.io/integrations/ai/mcp?token=secret")
        == "https://example.acryl.io/integrations/ai/mcp"
    )


def test_evidence_marker_is_auditable() -> None:
    marker = evidence_marker(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))

    assert "2026-07-23T12:00:00+00:00" in marker
    assert "explicit write-back approval" in marker
