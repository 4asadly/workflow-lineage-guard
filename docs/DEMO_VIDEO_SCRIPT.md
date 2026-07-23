# Demo video script

Target length: 2 minutes 40 seconds  
Maximum allowed length: 3 minutes

Do not record the live DataHub segment until `outputs/datahub-live-evidence.json` proves the
credentialed MCP calls. Never show API keys, tokens, `.env.local`, browser history, or terminal
environment output.

## 0:00–0:18 — The problem

**Screen:** Title, then the public demo hero.

**Voiceover:**

> A schema change can be valid in the warehouse and still break a customer-facing automation
> hours later. Workflow Lineage Guard connects DataHub lineage to the exact n8n expressions that
> depend on the changed field, before deployment.

## 0:18–0:42 — The input

**Screen:** Current schema, proposed schema, rename map, lineage path, and n8n workflow.

**Voiceover:**

> In this example, `customer_email` becomes `email_address`. The lineage path connects the
> Snowflake source to a customer profile and then to a renewal-alert workflow. The workflow JSON
> still references the old field.

## 0:42–1:12 — Run the impact scan

**Screen:** Click **Run impact scan**, then show the verdict, score, findings, and exact JSON
pointers.

**Voiceover:**

> The deterministic engine returns a 51 out of 100, needs-review verdict. It identifies the exact
> affected nodes and JSON pointers. This is evidence, not a model guess: the same input always
> produces the same result.

## 1:12–1:38 — Reviewable repair

**Screen:** Show each before-and-after patch and download the fixed workflow.

**Voiceover:**

> Because the rename is explicit, Lineage Guard generates boundary-safe replacements and a fixed
> workflow download. Removed fields without an approved replacement are blocked instead of being
> guessed.

## 1:38–2:02 — Architecture and safety

**Screen:** Open the architecture diagram in the repository.

**Voiceover:**

> DataHub provides schema and lineage context. Deterministic code owns reference detection and
> mutation. One OpenAI Agents SDK agent orchestrates those tools and explains the result. DataHub
> write-back has two approval gates, so mutation is never silently enabled.

## 2:02–2:27 — Real DataHub proof

**Record this segment only after the live preflight succeeds.**

**Screen:** A real dataset in the DataHub UI, the credential-safe evidence file, and the appended
verification marker in DataHub. Keep every token and environment value off screen.

**Voiceover:**

> Here is the same path against a real DataHub tenant. The verifier searches the catalog, reads
> the schema, queries downstream lineage, and—after explicit approval—appends an auditable
> description marker. The public evidence records tool names and outcomes without storing the
> token.

## 2:27–2:40 — Close

**Screen:** GitHub repository, Apache-2.0 license, green CI, and live-demo link.

**Voiceover:**

> Workflow Lineage Guard is Apache-2.0, reproducible without credentials, and ready for review.
> The source, tests, sample outputs, and live demo are public.

## Recording checklist

- Use 1080p or higher.
- Keep the cursor slow and deliberate.
- Zoom the browser so exact pointers are readable.
- Record one clean take; remove dead time.
- Add captions.
- Upload publicly to YouTube or Vimeo.
- Confirm the final runtime is under three minutes.
- Put the public video URL in `DEVPOST_SUBMISSION.md` and the Devpost submission.
