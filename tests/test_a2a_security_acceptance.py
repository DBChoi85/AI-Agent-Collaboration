"""Black-box security acceptance tests against a real A2A verification runner.

Set A2A_SECURITY_RUNNER to an executable that accepts a scenario name and
prints JSON: {"accepted": false, "task_dispatched": false, "reason": "..."}.
The runner MUST invoke the actual A2A receiving gateway and Besu registry;
mocked status/signature decisions do not constitute integration evidence.
"""
import json
import os
import subprocess
import unittest

SCENARIOS = {
    "valid": True,
    "revoked": False,
    "invalid_signature": False,
    "stale_request": False,
}

class A2ASecurityAcceptanceTests(unittest.TestCase):
    def test_acceptance_policy(self):
        runner = os.environ.get("A2A_SECURITY_RUNNER")
        if not runner:
            if os.environ.get("A2A_SECURITY_REQUIRED") == "1":
                self.fail("A2A_SECURITY_RUNNER is required for integration validation")
            self.skipTest("Real A2A security runner not configured")
        if not os.path.isfile(runner) or not os.access(runner, os.X_OK):
            self.fail("A2A_SECURITY_RUNNER must be an executable file")
        for scenario, expected in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                result = subprocess.run(
                    [runner, scenario], capture_output=True, text=True,
                    timeout=60, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                try:
                    data = json.loads(result.stdout)
                except json.JSONDecodeError as exc:
                    self.fail(f"{scenario}: invalid runner JSON: {exc}")
                self.assertIs(type(data.get("accepted")), bool)
                self.assertIs(type(data.get("task_dispatched")), bool)
                self.assertEqual(data["accepted"], expected)
                self.assertEqual(data["task_dispatched"], expected)
                self.assertIsInstance(data.get("reason"), str)
                self.assertTrue(data["reason"].strip())

if __name__ == "__main__":
    unittest.main()
