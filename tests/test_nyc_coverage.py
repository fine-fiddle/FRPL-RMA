import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from gather_nyc_coverage import AUDIT, EXTRACT, admissions_rows, audit, numeric


class NYCCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())

    def test_committed_audit_rebuilds(self):
        self.assertEqual(audit(self.payload), json.loads(AUDIT.read_text()))

    def test_same_year_income_is_required(self):
        payload = copy.deepcopy(self.payload)
        original = audit(payload)
        payload['demographics'] = [r for r in payload['demographics'] if r['YEAR'] != '2025']
        changed = audit(payload)
        for row in changed['assessment_coverage']:
            if row['year'] == 2025:
                self.assertEqual(row['numeric_join_with_valid_count'], 0)
            else:
                self.assertIn(row, original['assessment_coverage'])

    def test_suppression_and_duplicate_rejection(self):
        for value in ['s', '', '*', None]:
            self.assertIsNone(numeric(value))
        self.assertEqual(numeric('0'), 0)
        with self.assertRaises(ValueError):
            numeric('Above 95%')
        payload = copy.deepcopy(self.payload)
        payload['demographics'].append(payload['demographics'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            audit(payload)

    def test_multiple_programs_keep_own_priorities_and_vintage(self):
        rows = admissions_rows([dict(dbn='02M001', school_name='Example',
            program1='Open program', method1='Open', admissionspriority11='Local priority',
            program11='Audition program', method11='Audition', admissionspriority111='Citywide')])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['priorities'], {'admissionspriority11':'Local priority'})
        self.assertEqual(rows[1]['priorities'], {'admissionspriority111':'Citywide'})
        self.assertTrue(all(r['directory_year'] == 2021 for r in rows))

    def test_crosswalk_preserves_dbn_and_beds_without_name_join(self):
        rows = self.payload['crosswalk']
        self.assertTrue(rows)
        for row in rows:
            self.assertRegex(row['ATS System Code'], r'^\d{2}[MKQRX]\d{3}$')
        self.assertTrue(any(r['ATS System Code'].startswith('01') for r in rows))
        self.assertTrue(any(r['Managed By Name']=='Charter' for r in rows))
        self.assertEqual(audit(self.payload)['status'], 'gathered_not_published')


if __name__ == '__main__':
    unittest.main()
