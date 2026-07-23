# Security policy

## Supported version

Security fixes are currently applied to the latest `0.1.x` release and the default branch.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository when available. Do not open a
public issue containing a credential, a private DataHub endpoint, catalog metadata, or a client
workflow.

Include:

- the affected version or commit;
- a minimal synthetic reproduction;
- the potential impact;
- whether write-back or credential handling is involved.

## Credential handling

- Real values belong only in the ignored `.env.local` file.
- Evidence generation strips URL credentials and query parameters.
- Tokens must never appear in logs, screenshots, fixtures, issues, or generated evidence.
- Write-back requires both server enablement and explicit per-run approval.
