import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from plan_district_comparisons import (EXTRACT, membership_totals,
    potential_cohort, scope, size_tier, validate)


class DistrictPlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EXTRACT.read_text())
        cls.rows = {row['nces_lea_id']: row for row in cls.payload['agencies']}

    def test_native_district_totals_and_existing_scopes_are_preserved(self):
        validate(self.payload)
        # LEA totals differ from summing individual school membership. The
        # planning screen must use the independently published LEA population.
        self.assertEqual(self.rows['0622710']['enrollment'], 408026)
        self.assertNotEqual(self.rows['0622710']['enrollment'], 406717)
        self.assertEqual(self.rows['1709930']['enrollment'], 324130)
        self.assertEqual(self.rows['1709930']['scope'], 'existing_chicago')
        self.assertEqual(self.rows['1500030']['scope'], 'existing_hawaii_statewide')
        self.assertEqual(self.rows['3600077']['scope'], 'existing_nyc_component')
        self.assertEqual(self.rows['4800211']['scope'], 'other_agency_scope_review')
        self.assertEqual(self.rows['5102250']['scope'], 'district_charter_status_review')
        self.assertFalse(self.payload['approved_for_modeling'])
        self.assertFalse(self.payload['browser_catalog'])

    def test_duplicate_wrong_year_or_demographic_subtotal_is_rejected(self):
        original = self.rows['0622710']['membership_raw']
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            membership_totals([original, original])
        for field, value, pattern in [('SCHOOL_YEAR', '2023-2024', 'Wrong-year'),
                                      ('GRADE', 'Grade 3', 'demographic subtotal')]:
            bad = dict(original, **{field: value})
            with self.assertRaisesRegex(ValueError, pattern):
                membership_totals([bad])

    def test_foreign_identity_unreported_enrollment_and_false_approval_fail(self):
        for field, value, pattern in [('enrollment', 406717, 'enrollment differs'),
                                      ('native_lea_id', 'CA-0000000', 'identity differs')]:
            payload = copy.deepcopy(self.payload)
            payload['agencies'][0][field] = value
            with self.assertRaisesRegex(ValueError, pattern):
                validate(payload)
        payload = copy.deepcopy(self.payload)
        payload['agencies'][0]['membership_raw']['DMS_FLAG'] = 'Not reported'
        with self.assertRaisesRegex(ValueError, 'enrollment differs'):
            validate(payload)
        payload = copy.deepcopy(self.payload)
        payload['agencies'][0]['potential_school_ids']['ES'][0] = '120039000001'
        with self.assertRaisesRegex(ValueError, 'foreign or duplicated'):
            validate(payload)
        payload = copy.deepcopy(self.payload)
        payload['approved_for_modeling'] = True
        with self.assertRaisesRegex(ValueError, 'cannot grant modeling approval'):
            validate(payload)

    def test_high_school_population_cannot_hide_lower_grade_enrollment(self):
        profile = dict(IGOFFERED='As reported', GSHI='12')
        profile.update({field: 'No' for field in ['G_PK_OFFERED', 'G_KG_OFFERED',
            'G_UG_OFFERED', 'G_AE_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)]})
        profile['G_9_OFFERED'] = 'Yes'
        total = dict(STUDENT_COUNT='100', DMS_FLAG='Reported')
        grades = {'Grade 9': dict(total)}
        self.assertEqual(potential_cohort(profile, total, grades), 'HS')
        # Even when offers say no lower grades, the enrolled composition wins.
        grades['Grade 9']['STUDENT_COUNT'] = '90'
        grades['Kindergarten'] = dict(STUDENT_COUNT='10', DMS_FLAG='Reported')
        self.assertIsNone(potential_cohort(profile, total, grades))
        grades = {'Grade 9': dict(total)}
        profile['G_8_OFFERED'] = 'Yes'
        self.assertIsNone(potential_cohort(profile, total, grades))
        profile['G_8_OFFERED'] = 'No'
        profile['IGOFFERED'] = 'Adjusted'
        self.assertIsNone(potential_cohort(profile, total, grades))

    def test_primary_only_schools_and_missing_membership_are_not_potential_test_cohorts(self):
        profile = dict(IGOFFERED='As reported', GSHI='02')
        profile.update({field: 'No' for field in ['G_PK_OFFERED', 'G_KG_OFFERED',
            'G_UG_OFFERED', 'G_AE_OFFERED'] + [f'G_{g}_OFFERED' for g in range(1, 14)]})
        profile['G_2_OFFERED'] = 'Yes'
        total = dict(STUDENT_COUNT='100', DMS_FLAG='Reported')
        self.assertIsNone(potential_cohort(profile, total, {'Grade 2': dict(total)}))
        profile['GSHI'] = '03'; profile['G_3_OFFERED'] = 'Yes'
        self.assertEqual(potential_cohort(profile, total, {'Grade 3': dict(total)}), 'ES')
        self.assertIsNone(potential_cohort(profile,
            dict(STUDENT_COUNT='-9', DMS_FLAG='Not reported'), {'Grade 3': dict(total)}))

    def test_district_names_never_determine_identity_or_scope(self):
        cps = copy.deepcopy(self.rows['1709930']['directory_raw'])
        cps['LEAID'] = '9999999'
        self.assertEqual(scope(cps), 'new_district_candidate')
        union = dict(cps, LEAID='3620580', LEA_TYPE='3')
        self.assertEqual(scope(union), 'other_agency_scope_review')
        special = dict(cps, LEAID='3600135', LEA_TYPE='2')
        self.assertEqual(scope(special), 'nyc_special_population_review')
        self.assertIsNone(size_tier(100000, dict(ES=29, HS=29)))
        self.assertEqual(size_tier(40000, dict(ES=0, HS=35)), 'secondary')


if __name__ == '__main__':
    unittest.main()
