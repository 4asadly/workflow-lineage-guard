"""FastAPI service and CLI entry point for Workflow Lineage Guard."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env.local")
load_dotenv(ROOT / ".env")

from agent import run_guard_agent, runtime_status  # noqa: E402


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow: dict[str, Any]
    current_schema: dict[str, str] | list[dict[str, Any]]
    proposed_schema: dict[str, str] | list[dict[str, Any]]
    dataset_urn: str = "urn:li:dataset:(urn:li:dataPlatform:snowflake,raw.customers,PROD)"
    rename_map: dict[str, str] = Field(default_factory=dict)
    lineage_path: list[str] = Field(default_factory=list)
    allow_writeback: bool = False


app = FastAPI(
    title="Workflow Lineage Guard",
    version="0.1.0",
    description="Predict and repair automation breakage using DataHub context.",
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", **runtime_status()}


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return runtime_status()


@app.get("/api/demo")
async def demo() -> dict[str, Any]:
    return json.loads((ROOT / "data" / "demo_request.json").read_text())


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    try:
        return await run_guard_agent(request.model_dump())
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def run_demo(output: Path | None = None) -> dict[str, Any]:
    payload = json.loads((ROOT / "data" / "demo_request.json").read_text())
    result = asyncio.run(run_guard_agent(payload))
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def cli() -> None:
    parser = argparse.ArgumentParser(description="Workflow Lineage Guard")
    parser.add_argument("--demo", action="store_true", help="run the bundled offline scenario")
    parser.add_argument("--output", type=Path, help="write the demo report to a JSON file")
    parser.add_argument("--serve", action="store_true", help="start the web application")
    args = parser.parse_args()
    if args.demo:
        result = run_demo(args.output)
        print(
            json.dumps(
                {
                    "verdict": result["verdict"],
                    "risk_score": result["risk_score"],
                    "patches": len(result["patches"]),
                    "agent_mode": result["agent"]["mode"],
                },
                indent=2,
            )
        )
        return
    if args.serve or os.getenv("PORT"):
        import uvicorn

        uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
        return
    parser.print_help()


if __name__ == "__main__":
    cli()
