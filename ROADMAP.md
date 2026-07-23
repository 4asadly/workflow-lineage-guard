# Roadmap

Workflow Lineage Guard is an early release. Work is prioritized by evidence quality and safe
failure behavior rather than feature count.

## Release proof

- [ ] Verify search, schema, and lineage reads against a real DataHub tenant.
- [ ] Capture credential-safe `outputs/datahub-live-evidence.json`.
- [ ] Verify one controlled `update_description` append behind both approval gates.
- [ ] Publish a judge-accessible demo and a short live-run video.

## Workflow coverage

- [ ] Add regression fixtures for more n8n expression forms.
- [ ] Define an adapter contract for Make, Airflow, Prefect, and Dagster.
- [ ] Support column-level lineage evidence when the DataHub graph exposes it.
- [ ] Generate a pull-request-ready workflow patch without deploying it automatically.

## Reliability

- [ ] Add contract tests against recorded, sanitized DataHub MCP schemas.
- [ ] Add property-based tests for JSON-pointer traversal and replacement boundaries.
- [ ] Add an evidence format version and compatibility policy.
- [ ] Document rollback behavior for approved description updates.

Issues and pull requests should preserve the rule that uncertain replacements are never silently
applied.
