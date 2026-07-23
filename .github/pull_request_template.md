## Summary

Describe the behavior changed and why.

## Safety evidence

- [ ] The deterministic engine still owns schema comparison and JSON mutation.
- [ ] New repair behavior has a synthetic regression test.
- [ ] Removed fields without a verified replacement remain blocked.
- [ ] No credentials, private catalog output, or client workflow data are included.

## Verification

- [ ] `uv run pytest -q`
- [ ] `uv run ruff check .`

## User-visible impact

Describe changes to verdicts, risk scores, patches, provenance, or write-back behavior.
