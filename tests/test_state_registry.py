import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from state_registry import load_registry, reported_count, validate_registry


class StateRegistryTests(unittest.TestCase):
    def test_all_fifty_have_unique_official_identities_without_discovery_approval(self):
        registry = load_registry()
        self.assertEqual(len({s['id'] for s in registry['states']}), 50)
        self.assertEqual(len({s['fips'] for s in registry['states']}), 50)
        self.assertFalse(registry['browser_catalog'])
        self.assertTrue(all(not s['candidate_snapshot']['approved_for_modeling']
            for s in registry['states']))
        for mutate in [lambda r: r['states'].append(copy.deepcopy(r['states'][0])),
                       lambda r: r['states'][0]['candidate_snapshot'].update(approved_for_modeling=True),
                       lambda r: r['states'][0].update(fips='99')]:
            invalid = copy.deepcopy(registry)
            mutate(invalid)
            with self.assertRaises(ValueError):
                validate_registry(invalid)

    def test_only_explicit_reported_nonnegative_counts_are_available(self):
        self.assertEqual(reported_count({'DMS_FLAG': 'Reported', 'STUDENT_COUNT': '0'}), 0)
        self.assertEqual(reported_count({'DMS_FLAG': 'Reported', 'STUDENT_COUNT': '15'}), 15)
        for flag, token in [('Suppressed', '15'), ('Not Reported', '0'),
                            ('Reported', '-9'), ('Reported', '<10'), ('Reported', '15.5')]:
            self.assertIsNone(reported_count({'DMS_FLAG': flag, 'STUDENT_COUNT': token}))

    def test_blocker_evidence_supports_rendering_and_rejects_incomplete_claims(self):
        registry = load_registry()
        blocked = next(s for s in registry['states'] if s['status'] == 'audited_blocker')
        for evidence in [None, [], ['docs/source.md'], {}, {'guide': 'docs/source.md'},
                         {'guide': 'docs/source.md', 'summary': '   '}]:
            invalid = copy.deepcopy(registry)
            state = next(s for s in invalid['states'] if s['id'] == blocked['id'])
            state['blocker_evidence'] = evidence
            with self.assertRaises(ValueError):
                validate_registry(invalid)


if __name__ == '__main__':
    unittest.main()
