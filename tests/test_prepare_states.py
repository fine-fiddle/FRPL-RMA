"""District descriptors must remain part of the ordinary offline rebuild."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from prepare_states import adapter_scripts, prepare


class DistrictRebuildTests(unittest.TestCase):
    def test_district_and_state_rebuild_once_against_the_requested_database(self):
        # Discover the committed descriptors, rather than manufacturing a
        # district path that could hide an unsupported descriptor layout.
        scripts = adapter_scripts()
        district = ROOT / 'scripts/prepare_los_angeles.py'
        statewide = ROOT / 'scripts/prepare_california.py'
        self.assertIn(district, scripts)
        self.assertIn(statewide, scripts)
        with tempfile.TemporaryDirectory() as folder:
            requested = Path(folder) / 'isolated.sqlite'
            requested.write_bytes(b'No command may replace this test database')
            with patch('prepare_states.subprocess.run') as run, patch('builtins.print'):
                prepare(requested)
            commands = [call.args[0] for call in run.call_args_list]
            invoked = [Path(command[1]) for command in commands]
            self.assertEqual(invoked.count(district), 1)
            self.assertEqual(invoked.count(statewide), 1)
            self.assertEqual(len(invoked), len(set(invoked)))
            self.assertTrue(all(command[-2:]==['--database', str(requested.resolve())]
                                for command in commands))
            self.assertTrue(all(call.kwargs['check'] for call in run.call_args_list))
            self.assertEqual(requested.read_bytes(), b'No command may replace this test database')


if __name__ == '__main__':
    unittest.main()
