"""Verify real DataHub MCP reads and an optional controlled description write-back."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lineage_guard.live_evidence import (  # noqa: E402
    build_update_description_payload,
    evidence_marker,
    find_dataset_urn,
    jsonable,
    safe_endpoint,
    tool_schema,
)

PLACEHOLDERS = {"", "replace_me", "changeme", "your_key_here"}
REQUIRED_READ_TOOLS = {"search", "list_schema_fields", "get_lineage"}


def configured(value: str | None) -> bool:
    return bool(value and value.strip().lower() not in PLACEHOLDERS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create token-free evidence that Workflow Lineage Guard spoke to a real "
            "DataHub MCP server."
        )
    )
    parser.add_argument(
        "--query",
        default="customer renewals",
        help="Catalog search used to discover a test dataset.",
    )
    parser.add_argument(
        "--dataset-urn",
        default=None,
        help="Dataset to inspect. Defaults to DATAHUB_TEST_DATASET_URN or the first search hit.",
    )
    parser.add_argument(
        "--output",
        default="outputs/datahub-live-evidence.json",
        help="Credential-safe JSON evidence path.",
    )
    parser.add_argument(
        "--writeback",
        action="store_true",
        help=(
            "Append a timestamped verification marker. Also requires "
            "DATAHUB_ENABLE_WRITEBACK=true."
        ),
    )
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    return parser.parse_args()


def call_record(name: str, arguments: dict[str, Any], result: Any) -> dict[str, Any]:
    return {
        "tool": name,
        "arguments": arguments,
        "result": jsonable(result),
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv(".env.local", override=False)
    url = os.getenv("DATAHUB_MCP_URL")
    token = os.getenv("DATAHUB_TOKEN")
    if not configured(url) or "your-tenant" in (url or ""):
        raise RuntimeError("Set a real DATAHUB_MCP_URL in the ignored .env.local file.")
    if not configured(token):
        raise RuntimeError("Set a real DATAHUB_TOKEN in the ignored .env.local file.")

    requested_urn = args.dataset_urn or os.getenv("DATAHUB_TEST_DATASET_URN")
    headers = {"Authorization": f"Bearer {token}"}
    started_at = datetime.now(UTC)
    evidence: dict[str, Any] = {
        "kind": "workflow-lineage-guard-datahub-live-proof",
        "started_at": started_at.isoformat(),
        "endpoint": safe_endpoint(url),
        "auth": "bearer token supplied (value excluded)",
        "status": "running",
        "tool_inventory": [],
        "calls": [],
    }

    timeout = timedelta(seconds=max(1, args.timeout))
    async with streamablehttp_client(
        url,
        headers=headers,
        timeout=timeout,
        sse_read_timeout=timeout,
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            initialization = await session.initialize()
            evidence["server"] = jsonable(initialization)

            listed = await session.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            evidence["tool_inventory"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool_schema(tool),
                }
                for tool in listed.tools
            ]

            missing = sorted(REQUIRED_READ_TOOLS - tools.keys())
            if missing:
                raise RuntimeError(f"DataHub MCP is missing required read tools: {missing}")

            search_args = {"query": args.query}
            search_result = await session.call_tool("search", search_args)
            evidence["calls"].append(call_record("search", search_args, search_result))
            dataset_urn = requested_urn or find_dataset_urn(search_result)
            if not dataset_urn:
                raise RuntimeError(
                    "Search succeeded but no dataset URN was found. "
                    "Set DATAHUB_TEST_DATASET_URN to a dataset visible in DataHub."
                )
            evidence["dataset_urn"] = dataset_urn

            schema_args = {"urn": dataset_urn}
            schema_result = await session.call_tool("list_schema_fields", schema_args)
            evidence["calls"].append(
                call_record("list_schema_fields", schema_args, schema_result)
            )

            lineage_args = {"urn": dataset_urn, "upstream": False, "max_hops": 3}
            lineage_result = await session.call_tool("get_lineage", lineage_args)
            evidence["calls"].append(call_record("get_lineage", lineage_args, lineage_result))

            if args.writeback:
                if os.getenv("DATAHUB_ENABLE_WRITEBACK", "false").lower() != "true":
                    raise RuntimeError(
                        "--writeback also requires DATAHUB_ENABLE_WRITEBACK=true."
                    )
                if "update_description" not in tools:
                    raise RuntimeError(
                        "The server did not advertise update_description. "
                        "Enable DataHub MCP mutation tools first."
                    )
                write_schema = tool_schema(tools["update_description"])
                write_args = build_update_description_payload(
                    write_schema,
                    dataset_urn=dataset_urn,
                    description=evidence_marker(),
                )
                write_result = await session.call_tool("update_description", write_args)
                evidence["calls"].append(
                    call_record("update_description", write_args, write_result)
                )
                evidence["writeback"] = {
                    "attempted": True,
                    "tool": "update_description",
                    "operation": "append",
                }
            else:
                evidence["writeback"] = {
                    "attempted": False,
                    "reason": "Requires both --writeback and DATAHUB_ENABLE_WRITEBACK=true.",
                }

    evidence["completed_at"] = datetime.now(UTC).isoformat()
    evidence["status"] = "verified"
    evidence["proof_summary"] = {
        "real_server_initialized": True,
        "tool_inventory_captured": True,
        "catalog_search_completed": True,
        "schema_read_completed": True,
        "lineage_read_completed": True,
        "writeback_completed": bool(args.writeback),
    }
    return evidence


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    try:
        evidence = asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001 - CLI boundary emits a safe, actionable error.
        print(f"DataHub live verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    proof = evidence["proof_summary"]
    print(f"Verified DataHub MCP: {evidence['endpoint']}")
    print(f"Dataset: {evidence['dataset_urn']}")
    print(
        "Reads: search=yes, schema=yes, lineage=yes; "
        f"write-back={'yes' if proof['writeback_completed'] else 'no'}"
    )
    print(f"Credential-safe evidence: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
