import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from database import connect
from prepare_arizona import DATASET, EXTRACT, YEAR, assessment_values, count, income_values, import_data, level_for, sid


class ArizonaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.output = json.loads((ROOT/'data/arizona/schools.json').read_text())
        cls.history = json.loads((ROOT/'data/arizona/history.json').read_text())

    def test_native_bounds_and_suppression_never_become_numeric_proficiency(self):
        row = {'Percent Passing': '*', 'Number Tested': 100}
        for value in ['*', '<2%', '>98%', None]:
            row['Percent Passing'] = value
            self.assertEqual(assessment_values(row)[:2], (None, 100))
        self.assertIsNone(count('*'))
        for value in [-1, 10.1, float('nan')]:
            with self.assertRaises(ValueError):
                count(value)

    def test_published_bands_round_independently_and_missing_valid_counts_remain_missing(self):
        row = {'Percent Passing': 49, 'Number Tested': '*',
               'Percent Proficiency Level 1': 20, 'Percent Proficiency Level 2': 30,
               'Percent Proficiency Level 3': 35, 'Percent Proficiency Level 4': 15}
        self.assertEqual(assessment_values(row), (49, None, None))
        row['Percent Passing'] = 47
        with self.assertRaises(ValueError):
            assessment_values(row)
        row.update({'Percent Passing': 49, 'Percent Proficiency Level 1': 19})
        with self.assertRaises(ValueError):
            assessment_values(row)

    def test_individual_income_uses_only_native_same_table_counts(self):
        entry = {'all_students': {'raw': {'Total': 130}}, 'income': {'raw': {'Total': 39}}}
        self.assertEqual(income_values(entry), (130, 39, 30))
        entry['income']['raw']['Total'] = '*'
        entry['free'] = {'raw': {'Total': 39}}
        self.assertEqual(income_values(entry), (130, None, None))
        entry.pop('income')
        self.assertEqual(income_values(entry), (130, None, None))
        entry['income'] = {'raw': {'Total': 131}}
        with self.assertRaises(ValueError):
            income_values(entry)

    def test_suppressed_high_grade_presence_keeps_mixed_schools_out_of_grade_school_totals(self):
        entry = {'raw': {str(g): None for g in range(1, 13)}}
        entry['raw']['3'] = 45
        self.assertEqual(level_for(entry), 'ES')
        entry['raw']['9'] = '*'
        self.assertEqual(level_for(entry), 'HS')
        entry['raw']['9'] = 0
        self.assertEqual(level_for(entry), 'ES')
        entry['raw']['3'] = 0
        self.assertIsNone(level_for(entry))

    def test_authoritative_identity_year_and_population_validation(self):
        self.assertEqual(sid({'School Entity ID': 12345}), '12345')
        for value in ['12345', 123.5, 0, True]:
            with self.assertRaises(ValueError):
                sid({'School Entity ID': value})
        db = connect(':memory:')
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        entry = copy.deepcopy(self.payload['assessments'][0])
        with self.assertRaises(ValueError):
            import_data(db, dict(self.payload, assessments=[entry, entry]))
        for field, value in [('FiscalYear', 2024), ('FAY Status', 'FAY'), ('Subgroup', 'Income Eligibility 1 or 2'), ('Test Level', 'Alt Math Grade 11')]:
            altered = copy.deepcopy(entry)
            altered['raw'][field] = value
            with self.assertRaises(ValueError):
                import_data(db, dict(self.payload, assessments=[altered]))
        db.close()

    def test_importer_twice_preserves_unrelated_rows_and_native_tested_counts(self):
        db = connect(':memory:')
        db.executescript((ROOT/'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Keep','Keep','ready')")
        import_data(db, self.payload)
        tables = ['source', 'school', 'economic_observation', 'assessment_observation']
        first = [db.execute(f'SELECT * FROM {t} ORDER BY 1,2').fetchall() for t in tables]
        import_data(db, self.payload)
        self.assertEqual(first, [db.execute(f'SELECT * FROM {t} ORDER BY 1,2').fetchall() for t in tables])
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0], 'Keep')
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        for row in db.execute('SELECT tested, raw_value FROM assessment_observation WHERE dataset_id=?', (DATASET,)):
            self.assertEqual(row['tested'], count(json.loads(row['raw_value'])['Number Tested']))
        # A changed native district ID must not match on the school name.
        entry = copy.deepcopy(self.payload['assessments'][0])
        entry['raw']['District Entity ID'] = -1
        _, observations, ignored = import_data(db, dict(self.payload, assessments=[entry]))
        self.assertFalse(observations)
        self.assertEqual(ignored['Assessment and enrollment native district IDs differ'], 1)
        db.close()

    def test_output_uses_native_grade_populations_and_same_year_individual_income(self):
        profiles = {e['school_id']: e for e in self.payload['profiles']}
        raw = {(e['school_id'], e['raw']['Test Level'], e['raw']['Subject']): e['raw'] for e in self.payload['assessments']}
        for school in self.output['schools']:
            p = profiles[school['id']]
            self.assertEqual(school['level'], level_for(p))
            self.assertEqual(school['income'], income_values(p)[2])
            for subject, source_subject in [('math', 'Mathematics'), ('reading', 'English Language Arts')]:
                if subject not in school['metrics']:
                    continue
                test = 'All Assessments' if school['level']=='ES' else 'Math Grade 11' if subject=='math' else 'ELA Grade 11'
                source = raw[(school['id'], test, source_subject)]
                self.assertEqual(source['District Entity ID'], p['raw']['LEA Entity ID'])
                metric = school['metrics'][subject]
                self.assertEqual(metric['actual'], source['Percent Passing'])
                self.assertEqual(metric['tested'], count(source['Number Tested']))
            if 'combined' in school['metrics']:
                self.assertEqual(school['metrics']['combined']['actual'],
                                 (school['metrics']['math']['actual']+school['metrics']['reading']['actual'])/2)

    def test_six_models_match_independent_studentization_and_whole_model_interval_rule(self):
        for model in self.history['models']:
            rows = [r for r in self.history['records'] if r['level']==model['level'] and model['subject'] in r['subjects']]
            x = np.array([r['income'] for r in rows])
            y = np.array([r['subjects'][model['subject']]['actual'] for r in rows])
            X = np.column_stack([np.ones(len(x)), x])
            errors = y-X@np.linalg.lstsq(X, y, rcond=None)[0]
            h = np.einsum('ij,jk,ik->i', X, np.linalg.inv(X.T@X), X)
            expected = errors/np.sqrt((errors@errors-errors**2/(1-h))/(len(x)-3)*(1-h))
            np.testing.assert_allclose([r['subjects'][model['subject']]['studentized'] for r in rows], expected, atol=1e-8)
            self.assertEqual(model['n'], len(rows))
            missing = sum(r['subjects'][model['subject']]['tested'] is None for r in rows)
            self.assertEqual(missing, 0 if model['level']=='ES' else 9)
            for row in rows:
                self.assertEqual((row['year'], row['income_year']), (YEAR, YEAR))
                metric = row['subjects'][model['subject']]
                if model['level']=='HS':
                    self.assertIsNone(metric['low'])
                    self.assertIsNone(metric['high'])
                else:
                    self.assertIsNotNone(metric['low'])
                    self.assertIsNotNone(metric['high'])
        self.assertEqual(len(self.history['models']), 6)


if __name__ == '__main__':
    unittest.main()
