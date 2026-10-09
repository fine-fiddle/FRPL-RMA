import sys
import copy
import json
import unittest
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_data import build_history
from database import connect
from state_snapshot import import_snapshot


class SnapshotIntervalPolicyTests(unittest.TestCase):
    def frames(self, missing_count):
        incomes, assessments = [], []
        for i in range(20):
            incomes.append(dict(school_id=str(i), year='2025', name=str(i),
                enrollment=200, percentage=10 + i * 4, low_income=None,
                income_label='Audited individual eligibility'))
            for subject, offset in [('math', 0), ('reading', 5)]:
                assessments.append(dict(school_id=str(i), year='2025', level='ES',
                    assessment='Native school total', subject=subject,
                    proficiency=80 - i * 2 + (i % 3) + offset,
                    tested=None if missing_count and i == 0 and subject == 'math' else 100))
        return pl.DataFrame(assessments), pl.DataFrame(incomes)

    def test_one_missing_denominator_removes_intervals_from_entire_affected_models(self):
        records, models = build_history(*self.frames(True),
            point_only_assessments=['Native school total'])
        self.assertEqual({m['subject']: m['n'] for m in models},
            {'math': 20, 'reading': 20, 'combined': 20})
        for record in records:
            for subject in ['math', 'combined']:
                self.assertIsNone(record['subjects'][subject]['low'])
                self.assertIsNone(record['subjects'][subject]['high'])
                self.assertIsInstance(record['subjects'][subject]['studentized'], float)
            self.assertIsNotNone(record['subjects']['reading']['low'])
        full, _ = build_history(*self.frames(False))
        for actual, reference in zip(records, full):
            for subject in ['math', 'reading', 'combined']:
                self.assertEqual(actual['subjects'][subject]['studentized'],
                    reference['subjects'][subject]['studentized'])

    def test_missing_counts_need_explicit_assessment_approval(self):
        records, models = build_history(*self.frames(True))
        self.assertEqual({m['subject']: m['n'] for m in models},
            {'math': 19, 'reading': 20, 'combined': 19})
        missing = next(r for r in records if r['school_id'] == '0')
        self.assertNotIn('math', missing['subjects'])
        self.assertIn('Missing or fewer than 10 tested', missing['exclusions']['math'])

    def test_audit_hold_survives_reimport_and_invalid_status_preserves_store(self):
        extract = ROOT / 'data/source/maryland.json'
        payload = json.loads(extract.read_text())
        payload['schools'] = payload['schools'][:1]
        payload['release_status'] = 'audit_pending'
        db = connect(':memory:')
        self.addCleanup(db.close)
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        import_snapshot(db, payload, extract)
        import_snapshot(db, payload, extract)
        self.assertEqual(db.execute('SELECT status FROM dataset').fetchone()[0], 'audit_pending')
        before = [tuple(r) for r in db.execute('SELECT * FROM school')]
        bad = copy.deepcopy(payload); bad['release_status'] = 'published_anyway'
        with self.assertRaisesRegex(ValueError, 'release status'):
            import_snapshot(db, bad, extract)
        self.assertEqual(before, [tuple(r) for r in db.execute('SELECT * FROM school')])

    def test_duplicate_cohort_identity_level_or_assessment_preserves_store(self):
        extract = ROOT / 'data/source/maryland.json'
        payload = json.loads(extract.read_text())
        payload['schools'] = payload['schools'][:1]
        payload['cohorts'][0]['allow_point_only'] = False
        db = connect(':memory:')
        self.addCleanup(db.close)
        db.executescript((ROOT / 'scripts/schema.sql').read_text())
        import_snapshot(db, payload, extract)
        tables = ['dataset', 'source', 'school', 'assessment_definition',
                  'economic_definition', 'assessment_observation', 'economic_observation',
                  'model_run', 'model_result']
        def snapshot():
            return {table: [tuple(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                    for table in tables}
        before = snapshot()
        for collision, pattern in [('id', 'Duplicate or missing'),
                                   ('level', 'one cohort per school level'),
                                   ('assessment', 'distinct cohort assessment labels')]:
            with self.subTest(collision=collision):
                bad = copy.deepcopy(payload)
                extra = dict(bad['cohorts'][0], id='high', level='HS',
                             assessment='Different assessment', allow_point_only=True)
                extra[collision] = bad['cohorts'][0][collision]
                bad['cohorts'].append(extra)
                with self.assertRaisesRegex(ValueError, pattern):
                    import_snapshot(db, bad, extract)
                self.assertEqual(snapshot(), before)
        # The same label across ES/HS must be rejected before its HS permission
        # could allow a missing-count ES result into the grade-school model.
        self.assertFalse(payload['cohorts'][0]['allow_point_only'])
        self.assertIsNone(payload['schools'][0]['outcomes']['math']['tested'])


if __name__ == '__main__':
    unittest.main()
