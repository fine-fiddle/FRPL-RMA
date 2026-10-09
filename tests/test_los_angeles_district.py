import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_los_angeles as audit
import prepare_california as california


class LosAngelesDistrictAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(audit.OUTPUT.read_text())
        cls.payload = audit.load_california()

    def test_offline_exact_roster_keeps_source_holds_and_pure_cohorts(self):
        coverage = audit.validate(self.document, self.payload)
        self.assertEqual(coverage['directory_records'], 785)
        self.assertEqual(coverage['operational_schools'], 784)
        self.assertEqual(coverage['exact_supported_profile_matches'], 783)
        self.assertEqual(coverage['matched_scope'], {'ES': 589, 'HS': 147, 'mixed': 47})
        self.assertEqual(coverage['outside_roster_supported_prefix_profiles'], 218)
        self.assertFalse(self.document['approved_for_modeling'])
        for cohort, applicable, expected in [('pure_grade_schools', 572, [561, 561, 561]),
                                              ('pure_high_schools', 144, [137, 137, 136])]:
            value = self.document['cohorts'][cohort]
            self.assertEqual(value['applicable_profiles'], applicable)
            self.assertEqual([value['subjects'][s]['usable'] for s in ['math', 'reading', 'combined']], expected)
        self.assertEqual(self.document['cohorts']['mixed_grades_3_8']['subjects']['combined']['usable'], 30)
        self.assertEqual(self.document['cohorts']['mixed_grade_11']['subjects']['combined']['usable'], 32)
        self.assertNotIn('models', self.document)
        self.assertNotIn('snapshots', self.document)

    def test_reporting_prefix_cannot_expand_the_district_roster(self):
        outside = self.document['outside_roster_profiles']
        self.assertTrue(all(r['profile']['raw']['Charter School (Y/N)'].strip() == 'Yes' for r in outside))
        self.assertEqual(sum(r['assessment_type_ids'] == ['9'] for r in outside), 216)
        self.assertEqual(sum(r['assessment_type_ids'] == [] for r in outside), 2)
        roster = {r['school_id'] for r in self.document['roster_links']}
        self.assertFalse(roster.intersection(r['school_id'] for r in outside))
        unmatched = [r for r in self.document['roster_links'] if not r['matched']]
        self.assertEqual([r['school_id'] for r in unmatched], ['19647330117226'])
        self.assertNotIn('income', unmatched[0])
        self.assertEqual([r['school_id'] for r in self.document['nonoperational_directory']], ['19647330126474'])

    def test_normal_offline_replay_never_opens_raw_archives(self):
        with mock.patch.object(audit.zipfile, 'ZipFile', side_effect=AssertionError('Raw archives are unavailable')):
            self.assertEqual(audit.validate(self.document)['exact_supported_profile_matches'], 783)

    def test_wrong_year_duplicate_cross_lea_and_changed_provenance_fail(self):
        mutations = [
            lambda d: d.update(approved_for_modeling=True),
            lambda d: d.update(year=2024),
            lambda d: d['directory_records'][0]['raw'].update(SCHOOL_YEAR='2023-2024'),
            lambda d: d['directory_records'][0]['raw'].update(ST_LEAID='CA-1964725'),
            lambda d: d['directory_records'][0]['raw'].update(ST_SCHID='CA-1964725-6110951'),
            lambda d: d['directory_records'][0]['raw'].update(NCESSCH='060000000001'),
            lambda d: d['directory_records'][0].update(source_row=999999),
            lambda d: d['directory_records'].append(copy.deepcopy(d['directory_records'][0])),
            lambda d: d['sources']['ccd_school_directory'].update(sha256='0' * 64),
            lambda d: d['sources']['ca-frpm-2025'].update(url='https://example.invalid/income'),
        ]
        for mutation in mutations:
            changed = copy.deepcopy(self.document)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit.validate(changed, self.payload)

    def test_complete_flags_and_native_grade_bounds_are_required(self):
        matched = next(r for r in self.document['roster_links'] if r.get('scope') == 'ES')
        raw = next(r['raw'] for r in self.document['directory_records']
                   if r['source_row'] == matched['ccd_source_row'])
        self.assertEqual(audit.grade_agreement(raw, matched['profile']['raw']), 'ES')
        for field, value in [('G_9_OFFERED', 'Yes'), ('G_UG_OFFERED', 'Yes'),
                             ('G_8_OFFERED', ''), ('IGOFFERED', 'Imputed')]:
            changed = dict(raw, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.grade_agreement(changed, matched['profile']['raw'])
        changed_profile = dict(matched['profile']['raw'], **{'High Grade': '12'})
        with self.assertRaises(ValueError):
            audit.grade_agreement(raw, changed_profile)
        wrong = dict(raw, LEA_NAME='Same display name', SCH_NAME='Any school name')
        self.assertEqual(audit.directory_identity(wrong), matched['school_id'])

    def test_missing_grade_and_suppression_stay_unavailable(self):
        matched = next(r for r in self.document['roster_links'] if r.get('scope') == 'ES'
                       and r['assessments']['ES']['math']['usable'])
        source = matched['assessments']['ES']['math']
        rows = [dict(r['raw'], source_row=r['source_row']) for r in source['expected_grade_records']]
        expected = source['expected_grades']
        rate, tested, reason = california.aggregate(rows, expected)
        self.assertEqual((rate, tested, reason), (source['proficiency'], source['valid_scores'], None))
        suppressed = copy.deepcopy(rows)
        suppressed[0]['Count Standard Met and Above'] = '*'
        pct, count, reason = california.aggregate(suppressed, expected)
        result = audit.subject_record({'expected_grades': expected, 'raw': suppressed,
                                       'proficiency': pct, 'tested': count, 'exclusion': reason}, matched['income']['percentage'])
        self.assertFalse(result['usable'])
        self.assertIsNone(result['proficiency'])
        self.assertIsNone(result['valid_scores'])
        self.assertEqual(result['expected_grade_records'][0]['raw']['Count Standard Met and Above'], '*')
        total = dict(rows[0], Grade='13')
        self.assertIsNone(california.aggregate(rows[1:] + [total], expected)[0])
        self.assertFalse(audit.subject_record(None, matched['income']['percentage'])['applicable'])

    def test_count_suppression_and_pure_population_drift_fail_replay(self):
        for mutate in [
            lambda d: d['cohorts']['pure_grade_schools']['subjects']['combined'].update(usable=591),
            lambda d: d['cohorts']['pure_high_schools']['subjects']['combined'].update(usable=168),
            lambda d: d['outside_roster_profiles'].pop(),
            lambda d: d['roster_links'][0].update(scope='mixed'),
            lambda d: d['roster_links'][0]['assessments']['ES']['math'].update(valid_scores=100000),
            lambda d: d['roster_links'][0]['assessments']['ES']['math']['expected_grade_records'][0]['raw'].update(**{'Overall Total': '*'}),
        ]:
            changed = copy.deepcopy(self.document)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit.validate(changed, self.payload)
        changed_source = copy.deepcopy(self.payload)
        changed_source['assessments'][0][-2] = '*'
        with self.assertRaises(ValueError):
            audit.validate(self.document, changed_source)


if __name__ == '__main__':
    unittest.main()
