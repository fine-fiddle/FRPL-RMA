import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from database import ROOT
from prepare_nyc_types import classifications, program_types, TYPES


class NYCTypeTests(unittest.TestCase):
    def test_overlapping_and_specialized_types(self):
        types=classifications()
        self.assertIn('Gifted & Talented',types['03M334']['types'])
        self.assertIn('Specialized High School',types['02M475']['types'])
        self.assertEqual(set(types['03M485']['types']),{'Specialized High School','Audition / Arts'})
        self.assertTrue(any({'Zoned','Gifted & Talented'} <= set(r['types']) for r in types.values()))
        self.assertEqual(sum('Specialized High School' in r['types'] for r in types.values()),9)

    def test_no_inference_from_names_or_unknown_methods(self):
        p=dict(name='Gifted Arts Charter Academy',method=None,is_shs=False,is_lg=False,is_gt=False)
        self.assertEqual(program_types(p),set())
        with self.assertRaises(ValueError):
            program_types(dict(p,method='New Unknown Method'))
        self.assertEqual(program_types(dict(p,method='Talent Test')),{'Other / Special program'})

    def test_published_classifications_have_source_evidence(self):
        output=json.loads((ROOT/'data/nyc/schools.json').read_text())
        self.assertEqual(output['program_options'],TYPES)
        for school in output['schools']:
            tags=set(school['programs'])
            if tags=={'Unclassified'}:
                self.assertFalse(school['program_evidence'])
            else:
                self.assertNotIn('Unclassified',tags)
                self.assertEqual(tags,{t for e in school['program_evidence'] for t in e['types']})
                for evidence in school['program_evidence']:
                    self.assertTrue(evidence['url'].startswith('https://'))
                    if evidence.get('process'):
                        self.assertEqual(evidence['school_year'],'2025-26 School Year')


if __name__=='__main__':unittest.main()
