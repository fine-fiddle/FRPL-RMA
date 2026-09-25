import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_illinois import validate_counts


class CountsTests(unittest.TestCase):
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
