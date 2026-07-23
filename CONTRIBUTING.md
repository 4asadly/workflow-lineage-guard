# Contributing

Thank you for helping improve Workflow Lineage Guard. The project is intentionally conservative:
an uncertain repair should become a review or block decision, not a confident guess.

## Development setup

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
cp .env.example .env.local
uv run pytest -q
uv run ruff check .
uv run python main.py --demo
```

The test suite and deterministic demo do not require credentials.

## Contribution boundaries

- Keep schema comparison, reference extraction, and JSON mutation deterministic.
- Add a synthetic regression test for every new repair rule or workflow expression.
- Never commit API keys, DataHub tokens, private catalog output, or client workflow data.
- Do not weaken the two write-back gates.
- Label inferred mappings separately from explicit mappings.
- Preserve exact JSON-pointer evidence in every automatic patch.

For substantial adapters or behavior changes, open an issue before implementation so the evidence
contract and safety boundary can be agreed first.

## Pull requests

1. Keep each pull request focused on one behavior.
2. Run `uv run pytest -q` and `uv run ruff check .`.
3. Explain user-visible changes to verdicts, risk, provenance, or write-back.
4. Include before/after synthetic artifacts when the output format changes.

By contributing, you agree that your contribution is licensed under Apache License 2.0.
