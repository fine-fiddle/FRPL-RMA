import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT, connect
from prepare_massachusetts import BANDS, EXTRACT, GRADES, YEAR, band_for, import_data, income, result, school_id


class MassachusettsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.profiles = {r['school_id']: r for r in cls.payload['schools']}
        cls.observations = {(r['school_id'], r['raw']['test_grade'], r['raw']['subject_code']): r['raw']
                            for r in cls.payload['assessments']}
        cls.outputs = [json.loads((ROOT / 'data/massachusetts' / folder / 'schools.json').read_text())
                       for folder in ['', 'mixed']]

    def test_native_total_denominator_preserves_published_rounding(self):
        raw = dict(m_plus_e_pct='.36', m_plus_e_cnt='127', e_cnt='9', m_cnt='118',
                   pm_cnt='164', nm_cnt='65', stu_cnt='356', stu_part_pct='.99')
        self.assertEqual(result(raw), (36, 356))
        self.assertNotEqual(result(raw)[0], 100 * 127 / 356)
        # Participation is independent metadata, never the included-score count.
        self.assertEqual(result(dict(raw, stu_part_pct='.50')), (36, 356))
        for field, value in [('stu_cnt', '357'), ('e_cnt', '10'), ('m_plus_e_pct', '.38'),
                             ('stu_cnt', '356.5'), ('m_plus_e_cnt', None)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                result(dict(raw, **{field: value}))
        self.assertEqual(result(dict(raw, m_plus_e_pct='***')), (None, None))
        self.assertEqual(result({}), (None, None))

    def test_same_year_grade_scope_and_income_definition(self):
        self.assertEqual(len(self.profiles), 1817)
        self.assertEqual(school_id('00010015'), '00010015')
        for bad in [10015, '10015', '00010015.0', '00000000', '../00010015']:
            with self.assertRaises(ValueError):
                school_id(bad)
        for profile in self.profiles.values():
            raw = profile['raw']
            self.assertEqual(raw['sy'], str(YEAR))
            self.assertEqual(profile['band'], band_for(raw))
            total, low, pct = income(raw)
            if total:
                self.assertEqual(sum(int(raw[f]) for f in GRADES), total)
            if pct is not None:
                self.assertEqual(pct, 100 * float(raw['li_pct']))
                self.assertLessEqual(abs(low / total - pct / 100), .000500001)
        self.assertFalse(self.payload['excluded_assessments'])

    def test_native_total_outputs_and_complete_cohort_separation(self):
        expected = {'grade': (1396, 1228), 'high': (274, 242), 'mixed': (145, 126)}
        for output in self.outputs:
            for school in output['schools']:
                profile = self.profiles[school['id']]
                level, assessment, _, test_grade = BANDS[profile['band']]
                self.assertEqual(school['level'], level)
                self.assertEqual(school['history'][0]['assessment'], assessment)
                self.assertEqual(school['history'][0]['income_year'], YEAR)
                self.assertEqual(school['income'], income(profile['raw'])[2])
                for subject, code in [('math', 'MATH'), ('reading', 'ELA')]:
                    actual = result(self.observations.get((school['id'], test_grade, code), {}))
                    metric = school['metrics'].get(subject)
                    if metric:
                        self.assertEqual((metric['actual'], metric['tested']), actual)
                        self.assertIsNotNone(metric['low'])
                        self.assertIsNotNone(metric['high'])
                if 'combined' in school['metrics']:
                    self.assertAlmostEqual(school['metrics']['combined']['actual'],
                        (school['metrics']['math']['actual'] + school['metrics']['reading']['actual']) / 2)
                else:
                    self.assertTrue(school['exclusions']['combined'])
            for band in {self.profiles[s['id']]['band'] for s in output['schools']}:
                schools = [s for s in output['schools'] if self.profiles[s['id']]['band'] == band]
                self.assertEqual((len(schools), sum('combined' in s['metrics'] for s in schools)), expected[band])

    def test_models_against_independent_deleted_school_regressions(self):
        for output in self.outputs:
            for model in output['history_models']:
                cohort = [s for s in output['schools'] if s['history'][0]['assessment'] == model['assessment']
                          and model['subject'] in s['metrics']]
                x = np.array([s['income'] for s in cohort])
                y = np.array([s['metrics'][model['subject']]['actual'] for s in cohort])
                X = np.column_stack([np.ones(len(x)), x])
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                self.assertEqual(model['n'], len(x))
                self.assertAlmostEqual(model['slope'], beta[1], places=9)
                for i in [0, len(x) // 2, len(x) - 1]:
                    keep = np.arange(len(x)) != i
                    deleted = np.linalg.lstsq(X[keep], y[keep], rcond=None)[0]
                    errors = y[keep] - X[keep] @ deleted
                    variance = errors @ errors / (len(x) - 3)
                    leverage = X[i] @ np.linalg.inv(X.T @ X) @ X[i]
                    external = (y[i] - X[i] @ beta) / np.sqrt(variance * (1 - leverage))
                    self.assertAlmostEqual(cohort[i]['metrics'][model['subject']]['studentized'], external, places=8)

    def test_repeat_import_preserves_other_datasets_and_rejects_wrong_year(self):
        db = connect(':memory:')
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        db.execute("INSERT INTO dataset VALUES ('keep','IL','Unrelated','Keep','ready')")
        import_data(db, self.payload)
        tables = ['source', 'school', 'economic_observation', 'assessment_observation']
        before = {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables}
        import_data(db, self.payload)
        self.assertEqual(before, {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in tables})
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(db.execute("SELECT name FROM dataset WHERE id='keep'").fetchone()[0], 'Unrelated')
        for change in ['year', 'id', 'grade', 'duplicate']:
            bad = copy.deepcopy(self.payload)
            if change == 'year':
                bad['schools'][0]['raw']['sy'] = '2024'
            elif change == 'id':
                bad['assessments'][0]['school_id'] = '99999999'
            elif change == 'grade':
                bad['schools'][0]['raw']['g10_cnt'] = '1'
            else:
                bad['assessments'].append(bad['assessments'][0])
            with self.subTest(change=change), self.assertRaises(ValueError):
                import_data(db, bad)
        db.close()


if __name__ == '__main__':
    unittest.main()
