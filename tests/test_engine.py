import json
import unittest
from pathlib import Path

from lineage_guard.engine import analyze_workflow, diff_schemas, extract_references

ROOT = Path(__file__).resolve().parents[1]


class LineageGuardEngineTests(unittest.TestCase):
    def setUp(self):
        self.demo = json.loads((ROOT / "data" / "demo_request.json").read_text())

    def test_demo_rename_is_found_and_patched(self):
        report = analyze_workflow(
            self.demo["workflow"],
            self.demo["current_schema"],
            self.demo["proposed_schema"],
            dataset_urn=self.demo["dataset_urn"],
            rename_map=self.demo["rename_map"],
            lineage_path=self.demo["lineage_path"],
        )
        serialized = json.dumps(report.fixed_workflow)
        self.assertEqual(report.verdict, "needs_review")
        self.assertGreaterEqual(report.risk_score, 45)
        self.assertGreaterEqual(len(report.patches), 2)
        self.assertNotIn("$json.customer_email", serialized)
        self.assertIn("$json.email_address", serialized)
        self.assertEqual(report.provenance["source"], "request payload")
        self.assertFalse(report.provenance["datahub_verified"])

    def test_removed_field_without_replacement_blocks(self):
        report = analyze_workflow(
            {"name": "Alert", "nodes": [{"name": "Send", "value": "={{$json.phone}}"}]},
            {"phone": "string", "id": "string"},
            {"id": "string"},
        )
        self.assertEqual(report.verdict, "blocked")
        self.assertEqual(len(report.patches), 0)
        self.assertIn("no verified replacement", report.findings[0].explanation)

    def test_retype_requires_review_but_does_not_rewrite(self):
        workflow = {"name": "Billing", "nodes": [{"name": "Total", "value": "={{$json.amount}}"}]}
        report = analyze_workflow(workflow, {"amount": "string"}, {"amount": "number"})
        self.assertEqual(report.verdict, "needs_review")
        self.assertEqual(len(report.patches), 0)
        self.assertEqual(report.findings[0].severity, "warning")

    def test_unreferenced_breaking_change_is_safe_for_this_workflow(self):
        workflow = {"name": "Names", "nodes": [{"name": "Set", "value": "={{$json.name}}"}]}
        report = analyze_workflow(
            workflow,
            {"name": "string", "legacy_code": "string"},
            {"name": "string"},
        )
        self.assertEqual(report.verdict, "safe")
        self.assertEqual(report.risk_score, 0)

    def test_reference_evidence_contains_pointer_and_node(self):
        references = extract_references(self.demo["workflow"])
        hits = references["customer_email"]
        self.assertTrue(all(hit.json_pointer.startswith("/nodes/") for hit in hits))
        self.assertIn("Prepare CRM Payload", {hit.node_name for hit in hits})

    def test_explicit_rename_wins_over_inference(self):
        changes = diff_schemas(
            {"mail": "string"},
            {"primary_email": "string"},
            {"mail": "primary_email"},
        )
        self.assertEqual(changes[0].kind, "renamed")
        self.assertEqual(changes[0].replacement, "primary_email")
        self.assertEqual(changes[0].confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
