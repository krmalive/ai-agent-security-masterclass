from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lab_launch', ROOT / 'launch.py')
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)


class LabTests(unittest.TestCase):
    def test_hook_is_provisioned_for_lab_root_and_target_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / 'target-project'
            project.mkdir()
            with patch.object(launch, 'ROOT', root), patch.object(launch, 'PROJECT', project), \
                 patch.object(launch, 'BIN', root / 'bin' / 'juardrails'), \
                 patch.object(launch, 'cli', return_value=SimpleNamespace(returncode=0)), \
                 patch.object(launch.subprocess, 'run') as run:
                launch.prepare_pack()
            installed_at = [call.args[0][2] for call in run.call_args_list]
            self.assertEqual(installed_at, [str(root), str(project)])

    def test_requesty_helper_configures_claude_without_printing_key(self):
        with tempfile.TemporaryDirectory() as temp:
            credential = Path(temp) / 'requesty.env'
            credential.write_text('REQUESTY_API_KEY=synthetic-test-token\n'
                                  'BASE_URL=https://router.eu.requesty.ai/v1\n')
            script = ('source scripts/load-requesty.sh "$1"; '
                      'printf "|%s|%s|%s|%s|%s" "$ANTHROPIC_BASE_URL" '
                      '"$ANTHROPIC_MODEL" "$ANTHROPIC_DEFAULT_SONNET_MODEL" '
                      '"$ANTHROPIC_AUTH_TOKEN" "$(command -v juardrails)"')
            result = subprocess.run(['bash', '-c', script, 'bash', str(credential)],
                                    cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertIn('|https://router.eu.requesty.ai|azure/gpt-6-luna@eastus2|azure/gpt-6-luna@eastus2|synthetic-test-token|', result.stdout)
            self.assertIn('/bin/juardrails', result.stdout)
            self.assertNotIn('synthetic-test-token', result.stdout.split('|')[0])

    def test_three_tasks_start_with_expected_failures(self):
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                                cwd=ROOT / 'target-project', capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAILED (failures=9)', result.stderr)
        self.assertIn('Ran 13 tests', result.stderr)


if __name__ == '__main__':
    unittest.main()
