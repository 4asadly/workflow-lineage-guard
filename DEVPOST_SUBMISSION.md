# Devpost submission draft

## Project name

Workflow Lineage Guard

## Tagline

An agent that traces schema changes through DataHub, finds the automation workflows they will break, and generates evidence-backed JSON repairs before deployment.

## Challenge category

Agents That Do Real Work

## Inspiration

Automation failures often begin far upstream. A data team renames or removes one field; an n8n workflow continues expecting the old shape; customer follow-ups, CRM updates, or reporting pipelines fail later and far away from the original change. Traditional schema diff tools show what changed, but not which automation expression will break or how to repair it safely.

Workflow Lineage Guard turns DataHub's context graph into a pre-deployment safety system. It asks: if this source changes now, what breaks downstream, where is the exact reference, and is there a safe correction?

## What it does

1. Reads dataset schemas and upstream/downstream paths through DataHub MCP.
2. Compares the current and proposed schema.
3. Parses an exported n8n workflow and records exact JSON pointers for referenced fields.
4. Scores deployment risk and distinguishes safe, review-required, and blocked changes.
5. Generates a patched workflow JSON only when a replacement is explicit or unambiguous.
6. Produces an evidence report that can be written back to the affected DataHub dataset, so the next engineer or agent inherits the warning.

The bundled demo remains fully functional without credentials. Live mode adds an OpenAI Agents SDK agent, DataHub schema and lineage verification, and an explicitly approved DataHub description update.

The bundled report uses synthetic request data. A live DataHub claim should be added to the final
submission only after `scripts/datahub_preflight.py` records the required MCP calls against a real
tenant.

## How we built it

- DataHub MCP Server for `search`, `get_lineage`, `get_lineage_paths_between`, `list_schema_fields`, and approved `update_description` calls.
- OpenAI Agents SDK for a single cautious agent with deterministic workflow-analysis tools.
- A Python schema-diff and n8n expression scanner that records exact evidence and applies boundary-safe replacements.
- FastAPI and a responsive vanilla web interface for judge-friendly testing.
- Offline fixtures and unit tests so core safety behavior is reproducible without private credentials.

## Challenges

The biggest design challenge was preventing the language model from inventing a plausible field replacement. We separated responsibilities: DataHub provides trusted context, deterministic code performs the schema diff and JSON mutation, and the agent orchestrates tools and explains evidence. Removed fields without a verified replacement stop deployment instead of being guessed.

We also made write-back an explicit approval boundary. Mutation tools are not exposed unless both the server configuration and the user's request allow them.

## Accomplishments

- Exact workflow evidence down to the JSON pointer and n8n node name.
- Reviewable before/after patches rather than opaque regenerated workflow files.
- Graceful deterministic fallback when OpenAI or DataHub is unavailable.
- Read/write context-graph design that helps future people and agents avoid the same incident.
- Apache-2.0 repository with sample inputs, outputs, tests, and setup instructions.

## What we learned

Reliable data agents need more than a capable model. DataHub's lineage and schema context establish what is true; deterministic repair rules establish what is safe; the agent connects those parts into an understandable decision.

## What's next

- Support additional workflow formats such as Make, Airflow, Prefect, and Dagster.
- Learn approved rename mappings from DataHub change proposals and version-control pull requests.
- Add pull-request generation for patched workflow artifacts.
- Create an open-source DataHub skill for automation-impact analysis.

## Built with

DataHub, DataHub MCP Server, OpenAI Agents SDK, Python, FastAPI, Uvicorn, JavaScript, HTML, CSS, n8n JSON

## Testing instructions

Fastest path:

1. Open the [interactive browser demo](https://workflow-lineage-guard-demo.sweet-hake-1733.chatgpt.site).
2. Click **Run impact scan**. The bundled example renames `customer_email` to `email_address`,
   identifies the exact affected n8n JSON pointers, and produces reviewable patches plus a
   DataHub write-back preview.

Local path:

1. Clone the public repository.
2. Install dependencies with `uv sync --extra dev`.
3. Copy `.env.example` to `.env.local`; credentials are optional for the demo.
4. Run `uv run python main.py --demo --output examples/demo_report.json`.
5. Run `uv run python main.py --serve` and open `http://localhost:8000`.

## Required links before submission

- Public repository: https://github.com/4asadly/workflow-lineage-guard
- Live demo: https://workflow-lineage-guard-demo.sweet-hake-1733.chatgpt.site
- Public video under three minutes: `[ADD YOUTUBE OR VIMEO URL]`

## Submission checklist

- [ ] Join the hackathon while logged into Devpost.
- [ ] Capture credential-safe proof from a real DataHub tenant.
- [x] Add public repository and make Apache-2.0 visible in the repository About section.
- [x] Deploy a free judge-accessible demo.
- [ ] Record and upload a public demo video under three minutes.
- [x] Include `examples/` outputs in the repository.
- [ ] Complete the feedback-prize form.
- [ ] Submit before August 10, 2026 at 5:00 PM EDT (August 11 at 2:00 AM PKT); internal target: August 9.
