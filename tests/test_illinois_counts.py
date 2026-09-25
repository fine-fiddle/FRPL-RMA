import sys
from pathlib import Path
import unittest
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_illinois import validate_counts


class CountsTests(unittest.TestCase):
    def test_statewide_directory_and_history(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads((root/'data/illinois/schools.json').read_text())
        historical = json.loads((root/'data/source/illinois-history-2023.json').read_text())
        income = {p['RCDTS']: p['% Student Enrollment - Low Income'] for p in historical['profiles']}
        minooka = [s for s in data['schools'] if 'Minooka' in s['name']]
        self.assertEqual({s['name'] for s in minooka}, {'Minooka Jr High School', 'Minooka Elem School', 'Minooka Intermediate School'})
        for school in data['schools']:
            self.assertEqual(school['metrics'], next(r['subjects'] for r in school['history'] if r['year'] == 2024))
            for r in school['history']:
                if r['year'] == 2023 and r['subjects']:
                    self.assertEqual(r['income'], float(income[school['id']]))
                for subject, m in r['subjects'].items():
                    model = next(x for x in data['history_models'] if x['year']==r['year'] and x['subject']==subject)
                    self.assertAlmostEqual(m['predicted'], model['intercept']+model['slope']*r['income'])
                    self.assertAlmostEqual(m['residual'], m['actual']-m['predicted'])
                    self.assertLessEqual(m['low'], m['studentized'])
                    self.assertGreaterEqual(m['high'], m['studentized'])
        self.assertTrue(all(len(s['history']) == 2 for s in minooka))

    def rows(self):
        return [dict(GradeLevel='G03', StudentSubGroup_TotalTested='20', ProficientOrAbove_percent='.5'),
                dict(GradeLevel='G04', StudentSubGroup_TotalTested='30', ProficientOrAbove_percent='.8')]

    def test_weighted_reconciliation(self):
        self.assertEqual(validate_counts(self.rows(), 68, 'K - 4'), 50)
        self.assertIsNone(validate_counts(self.rows(), 65, 'K - 4'))

    def test_incomplete_and_duplicate_grades(self):
        self.assertIsNone(validate_counts(self.rows(), 68, 'K - 5'))
        self.assertIsNone(validate_counts(self.rows()*2, 68, 'K - 4'))

    def test_suppressed_range_missing_zero(self):
        for value in ['*', '--', '10-19', None, '0', '-10', '20.5']:
            rows = self.rows()
            rows[0]['StudentSubGroup_TotalTested'] = value
            self.assertIsNone(validate_counts(rows, 68, 'K - 4'))

    def test_missing_or_invalid_proficiency(self):
        self.assertIsNone(validate_counts(self.rows(), None, 'K - 4'))
        rows = self.rows()
        rows[0]['ProficientOrAbove_percent'] = 'nan'
        self.assertIsNone(validate_counts(rows, 68, 'K - 4'))
