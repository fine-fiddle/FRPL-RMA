import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_new_hampshire_directory import OUTPUT, directory_scope, native_integer, validate


class NewHampshireDirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(OUTPUT.read_text())

    def test_same_year_exact_id_crosswalk_remains_source_only(self):
        coverage = validate(self.document)
        self.assertEqual(coverage['exact_native_id_matches'], 483)
        self.assertEqual(coverage['income_schools'], 485)
        self.assertEqual(coverage['NH_directory_records'], 518)
        self.assertEqual(coverage['matched_offered_grade_scope'],
                         {'grade_school': 382, 'high_school': 77, 'other_grade_population': 24})
        self.assertEqual({(r['district_id'], r['school_id']) for r in self.document['unmatched_income']},
                         {(457, 29196), (457, 29197)})
        self.assertFalse(self.document['approved_for_modeling'])
        self.assertNotIn('assessment_records', self.document)
        self.assertNotIn('snapshots', self.document)

    def test_names_cannot_resolve_or_change_native_identity(self):
        changed = copy.deepcopy(self.document)
        for record in changed['income_records']:
            record['raw']['School Name'] = 'Same unrelated display name'
            record['raw']['District Name'] = 'Another display name'
        for record in changed['directory_records']:
            record['raw']['SCH_NAME'] = 'A different display name'
            record['raw']['LEA_NAME'] = 'Another unrelated display name'
        self.assertEqual(validate(changed), self.document['coverage'])
        changed['income_records'][0]['raw']['School #'] += 1
        with self.assertRaises(ValueError):
            validate(changed)

    def test_year_id_scope_and_duplicate_mutations_are_rejected(self):
        mutations = [
            lambda d: d.update(year=2024),
            lambda d: d.update(approved_for_modeling=True),
            lambda d: d['directory_records'][0]['raw'].update(SCHOOL_YEAR='2023-2024'),
            lambda d: d['directory_records'][0]['raw'].update(ST_LEAID='NH-999'),
            lambda d: d['matches'][0].update(ncessch='330000000000'),
            lambda d: d['matches'][0].update(offered_grade_scope='high_school'),
            lambda d: d['coverage'].update(exact_native_id_matches=484),
            lambda d: d['sources']['directory'].update(sha256='0' * 64),
            lambda d: d['unmatched_income'].clear(),
            lambda d: d['directory_records'].append(copy.deepcopy(d['directory_records'][0])),
            lambda d: d['income_records'].append(copy.deepcopy(d['income_records'][0])),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.document)
                mutation(changed)
                with self.assertRaises(ValueError):
                    validate(changed)
        for records, row_field in [('directory_records', 'source_record'), ('income_records', 'source_row')]:
            changed = copy.deepcopy(self.document)
            duplicate = copy.deepcopy(changed[records][0])
            duplicate[row_field] = 9999999
            changed[records].append(duplicate)
            with self.subTest(records=records), self.assertRaises(ValueError):
                validate(changed)
        for value in [True, False, 1.5, '21745', None, 0, -1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                native_integer(value)

    def test_unknown_high_mixed_and_postgraduate_offerings_are_preserved(self):
        raw = next(r['raw'] for r in self.document['directory_records'] if directory_scope(r['raw']) == 'grade_school')
        for field, value, expected in [
            ('G_9_OFFERED', 'Yes', 'mixed'),
            ('G_UG_OFFERED', 'Yes', 'other_grade_population'),
            ('G_13_OFFERED', 'Yes', 'other_grade_population'),
            ('G_9_OFFERED', '', 'uncertain_grade_reporting'),
            ('IGOFFERED', 'Imputed', 'uncertain_grade_reporting'),
            ('SY_STATUS', '2', 'nonoperational'),
        ]:
            with self.subTest(field=field, value=value):
                self.assertEqual(directory_scope(dict(raw, **{field: value})), expected)


if __name__ == '__main__':
    unittest.main()
