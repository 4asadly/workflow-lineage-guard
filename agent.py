"""OpenAI Agents SDK orchestration with DataHub MCP and an offline-safe fallback."""

from __future__ import annotations

import json
import os
from typing import Any

from lineage_guard.engine import analyze_workflow

PLACEHOLDER_VALUES = {"", "replace_me", "changeme", "your_key_here"}
DATAHUB_READ_TOOLS = {"search", "list_schema_fields", "get_lineage"}


def _configured(value: str | None) -> bool:
    if value is None or value.strip().lower() in PLACEHOLDER_VALUES:
        return False
    return len(value.strip()) >= 12


def runtime_status() -> dict[str, Any]:
    openai_ready = _configured(os.getenv("OPENAI_API_KEY"))
    datahub_ready = os.getenv("DATAHUB_MODE", "demo").lower() == "live" and _configured(
        os.getenv("DATAHUB_MCP_URL")
    )
    return {
        "mode": "live-agent" if openai_ready and datahub_ready else "demo",
        "openai_ready": openai_ready,
        "datahub_ready": datahub_ready,
        "writeback_server_enabled": os.getenv("DATAHUB_ENABLE_WRITEBACK", "false").lower()
        == "true",
        "message": (
            "OpenAI Agent + DataHub MCP ready."
            if openai_ready and datahub_ready
            else "Demo engine active. Add real credentials to .env.local for live MCP reasoning."
        ),
    }


def deterministic_scan(payload: dict[str, Any]) -> dict[str, Any]:
    report = analyze_workflow(
        payload["workflow"],
        payload["current_schema"],
        payload["proposed_schema"],
        dataset_urn=payload.get(
            "dataset_urn", "urn:li:dataset:(urn:li:dataPlatform:demo,customers,PROD)"
        ),
        rename_map=payload.get("rename_map"),
        lineage_path=payload.get("lineage_path"),
    )
    result = report.to_dict()
    result["agent"] = {
        "mode": "deterministic-demo",
        "narrative": report.summary,
        "writeback_status": "preview_only",
    }
    return result


def _called_tool_names(run_result: Any) -> set[str]:
    """Return tool names recorded by the Agents SDK without exposing arguments or output."""
    names: set[str] = set()
    for item in getattr(run_result, "new_items", []):
        name = getattr(item, "tool_name", None)
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _called(names: set[str], expected: str) -> bool:
    """Match plain and server-prefixed MCP tool names."""
    return any(
        name == expected
        or name.endswith(f".{expected}")
        or name.endswith(f"__{expected}")
        for name in names
    )


async def run_guard_agent(payload: dict[str, Any]) -> dict[str, Any]:
    """Run live only when both credentials are configured; otherwise degrade cleanly."""
    status = runtime_status()
    baseline = deterministic_scan(payload)
    if status["mode"] != "live-agent":
        baseline["agent"]["warning"] = status["message"]
        return baseline

    # Lazy imports keep offline demo mode usable without the API dependency installed.
    from agents import Agent, Runner, function_tool
    from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter

    @function_tool
    def inspect_workflow_impact() -> str:
        """Inspect the workflow deterministically and return evidence plus a safe patch."""
        return json.dumps(baseline, ensure_ascii=False)

    allow_writeback = bool(payload.get("allow_writeback")) and status["writeback_server_enabled"]
    allowed_tools = ["search", "get_lineage", "get_lineage_paths_between", "list_schema_fields"]
    if allow_writeback:
        allowed_tools.append("update_description")

    headers: dict[str, str] = {}
    token = os.getenv("DATAHUB_TOKEN")
    if _configured(token):
        headers["Authorization"] = f"Bearer {token}"

    server = MCPServerStreamableHttp(
        name="DataHub Context Graph",
        params={"url": os.environ["DATAHUB_MCP_URL"], "headers": headers},
        cache_tools_list=True,
        tool_filter=create_static_tool_filter(allowed_tool_names=allowed_tools),
    )
    try:
        async with server:
            writeback_instruction = (
                "After explaining the risk, call update_description once with the supplied "
                "write-back markdown."
                if allow_writeback
                else "Do not mutate DataHub. Present the write-back as a preview only."
            )
            agent = Agent(
                name="Workflow Lineage Guard",
                model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
                instructions=(
                    "You are a cautious data reliability agent. Use DataHub MCP to verify "
                    "the dataset schema and downstream lineage. Then call "
                    "inspect_workflow_impact for exact JSON evidence and deterministic repair. "
                    "Never invent a field mapping. Clearly separate "
                    f"verified evidence from inference. {writeback_instruction}"
                ),
                tools=[inspect_workflow_impact],
                mcp_servers=[server],
                mcp_config={
                    "convert_schemas_to_strict": True,
                    "include_server_in_tool_names": True,
                },
            )
            prompt = (
                f"Assess workflow '{baseline['workflow_name']}' against dataset "
                f"{baseline['dataset_urn']}. Verify schema and lineage, inspect exact breakage, "
                "and explain whether the generated patch is safe."
            )
            result = await Runner.run(agent, prompt, max_turns=10)
            tool_names = _called_tool_names(result)
            verified_reads = all(_called(tool_names, name) for name in DATAHUB_READ_TOOLS)
            writeback_published = _called(tool_names, "update_description")
            baseline["provenance"].update(
                {
                    "source": (
                        "DataHub MCP + request payload"
                        if verified_reads
                        else "request payload; DataHub MCP session connected"
                    ),
                    "datahub_verified": verified_reads,
                    "datahub_tool_calls": sorted(
                        name
                        for name in tool_names
                        if any(
                            _called({name}, expected)
                            for expected in DATAHUB_READ_TOOLS | {"update_description"}
                        )
                    ),
                }
            )
            baseline["agent"] = {
                "mode": "openai-agents-sdk",
                "narrative": str(result.final_output),
                "writeback_status": (
                    "published"
                    if writeback_published
                    else "approved_but_not_confirmed"
                    if allow_writeback
                    else "preview_only"
                ),
            }
            return baseline
    except Exception as exc:  # noqa: BLE001 - API boundary must fail gracefully for judges.
        baseline["agent"] = {
            "mode": "deterministic-fallback",
            "narrative": baseline["summary"],
            "writeback_status": "preview_only",
            "warning": (
                f"Live agent unavailable; deterministic evidence preserved ({type(exc).__name__})."
            ),
        }
        return baseline
