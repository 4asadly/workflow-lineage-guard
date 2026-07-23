import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import _called, _called_tool_names, runtime_status


class AgentFallbackTests(unittest.TestCase):
    def test_placeholder_key_keeps_demo_mode(self):
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "replace_me", "DATAHUB_MODE": "demo"},
            clear=False,
        ):
            status = runtime_status()
        self.assertEqual(status["mode"], "demo")
        self.assertFalse(status["openai_ready"])

    def test_writeback_is_off_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            status = runtime_status()
        self.assertFalse(status["writeback_server_enabled"])

    def test_agent_tool_calls_are_recorded_without_payloads(self):
        result = SimpleNamespace(
            new_items=[
                SimpleNamespace(tool_name="mcp_DataHub_Context_Graph__search"),
                SimpleNamespace(tool_name="inspect_workflow_impact"),
                SimpleNamespace(tool_name=None),
            ]
        )
        names = _called_tool_names(result)
        self.assertEqual(
            names,
            {"mcp_DataHub_Context_Graph__search", "inspect_workflow_impact"},
        )
        self.assertTrue(_called(names, "search"))
        self.assertFalse(_called(names, "update_description"))


if __name__ == "__main__":
    unittest.main()
