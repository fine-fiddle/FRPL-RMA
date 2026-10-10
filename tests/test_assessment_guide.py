import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import ROOT
from export_assessment_guide import (
    BOUNDARY_SHA256, PSAT_SOURCE_ID, PSAT_SOURCE_SHA256,
    PROVIDER_EVIDENCE_PATH, PROVIDER_EVIDENCE_SHA256,
    assessment_family, build_guide, extract_boundaries, local_path,
    load_provider_evidence, provider_binding, registry_states, signed_area, simplify_line, simplify_ring,
    validate_boundaries,
)


class AssessmentGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'data/manifest.json').read_text())
        cls.registry = json.loads((ROOT / 'data/source/state-expansion.json').read_text())
        cls.guide = build_guide(cls.manifest, cls.registry)
        cls.geometry = json.loads((ROOT / 'data/us-states.geojson').read_text())
        cls.by_state = {s['id']: s for s in cls.guide['states']}

    def test_all_fifty_statuses_and_blocker_guides_remain_visible(self):
        self.assertEqual(len(self.guide['states']), 50)
        registry = {s['id']: s for s in self.registry['states']}
        self.assertEqual(set(self.by_state), set(registry))
        self.assertEqual(len({s['fips'] for s in self.guide['states']}), 50)
        self.assertEqual(self.guide['states'], sorted(self.guide['states'], key=lambda s: s['name']))
        for state in self.guide['states']:
            with self.subTest(state=state['id']):
                source = registry[state['id']]
                self.assertEqual(state['status'], source['status'])
                self.assertEqual(state['fips'], source['fips'])
                self.assertEqual(state['name'], source['name'])
                self.assertIsNone(state.get('ambition_comparison'))
                if not state['assessments']:
                    self.assertEqual(state['guide'], source['blocker_evidence']['guide'])
                    self.assertEqual(state['blocker_summary'], source['blocker_evidence']['summary'])
                    self.assertTrue((ROOT / state['guide']).is_file())
        # These metadata definitions exist in SQLite/catalog but the Utah
        # comparison remains held, so its definition must not appear as released.
        self.assertTrue(any(d['state'] == 'UT' for d in self.manifest['assessments']))
        self.assertEqual(self.by_state['UT']['assessments'], [])
        self.assertIn('audit', self.by_state['UT']['blocker_summary'])

    def test_latest_ready_dataset_population_and_exact_native_standards(self):
        ready = {(s['id'], r['dataset']) for s in self.manifest['states']
                 for r in s['regions'] if r['status'] == 'ready'}
        eligible = [d for d in self.manifest['assessments']
                    if (d['state'], d['id'].split(':')[0]) in ready]
        latest = {}
        for definition in eligible:
            key = (definition['id'].split(':')[0], definition['level'])
            latest[key] = max(latest.get(key, 0), definition['year'])
        expected = {d['id']: d for d in eligible
                    if d['year'] == latest[(d['id'].split(':')[0], d['level'])]}
        actual = {a['id']: a for state in self.guide['states'] for a in state['assessments']}
        self.assertEqual(set(actual), set(expected))
        for key, row in actual.items():
            with self.subTest(definition=key):
                for field in ['id', 'state', 'name', 'year', 'level', 'grades', 'standard', 'source_url']:
                    self.assertEqual(row[field], expected[key][field])
                self.assertEqual(row['dataset_id'], key.split(':')[0])
                self.assertIsNone(row['ambition_comparison'])
                self.assertTrue(row['regions'])

    def test_regional_years_and_mixed_grade_scopes_do_not_collapse(self):
        new_york = self.by_state['NY']['assessments']
        latest = {a['dataset_id']: a['year'] for a in new_york if a['level'] == 'ES'}
        self.assertEqual(latest['nyc'], 2026)
        self.assertEqual(latest['ny-src-2025-grade'], 2025)
        statewide = next(a for a in new_york if a['dataset_id'] == 'ny-src-2025-grade')
        self.assertEqual([r['id'] for r in statewide['regions']], ['new-york'])
        wisconsin = self.by_state['WI']['assessments']
        mixed = next(a for a in wisconsin if 'mixed grade spans' in a['name'])
        ordinary = next(a for a in wisconsin if 'grades 9–11' in a['name'])
        self.assertEqual(mixed['level'], 'HS')
        self.assertEqual([r['id'] for r in mixed['regions']], ['wisconsin-mixed'])
        self.assertEqual([r['id'] for r in ordinary['regions']], ['wisconsin-totals'])
        for state in self.guide['states']:
            for assessment in state['assessments']:
                for region in assessment['regions']:
                    parsed = urlsplit(region['url'])
                    self.assertEqual(parsed.path, './')
                    self.assertEqual(parsed.netloc, '')
                    self.assertEqual(parse_qs(parsed.query), dict(state=[state['id']], region=[region['id']],
                                                                  level=[assessment['level']]))
                    self.assertIsInstance(region['model_scope'], str)
        # Dual-population regions otherwise default to ES. High-school definition
        # links must explicitly restore HS instead of silently opening grade schools.
        for state_id, region_id in [('CA', 'california'), ('DE', 'delaware'), ('WI', 'wisconsin-totals')]:
            high_school = next(a for a in self.by_state[state_id]['assessments']
                               if a['level'] == 'HS' and any(r['id'] == region_id for r in a['regions']))
            link = next(r['url'] for r in high_school['regions'] if r['id'] == region_id)
            self.assertEqual(parse_qs(urlsplit(link).query)['level'], ['HS'])

    def test_provider_is_explicitly_bound_to_audited_owner_evidence(self):
        rows = [a for state in self.guide['states'] for a in state['assessments']]
        published = [a for a in rows if a['provider'] is not None]
        self.assertEqual(len(published), 10)
        psat = next(a for a in published if a['provider'] == 'College Board')
        self.assertEqual((psat['state'], psat['dataset_id'], psat['year']), ('MI', 'mi-psat8-2025', 2025))
        self.assertEqual(psat['provider'], 'College Board')
        source = next(s for s in self.guide['sources'] if s['id'] == PSAT_SOURCE_ID)
        self.assertEqual(source['sha256'], PSAT_SOURCE_SHA256)
        self.assertEqual(psat['provider_source_url'], source['url'])
        self.assertEqual(psat['provider_role'], 'Assessment owner and publisher')
        self.assertEqual(psat['provider_evidence_ids'], [PSAT_SOURCE_ID])
        self.assertIn('390', psat['standard'])
        self.assertIn('430', psat['standard'])
        for row in rows:
            if row['provider'] is None:
                self.assertIsNone(row['provider_source_url'])
                self.assertIsNone(row['provider_role'])
                self.assertEqual(row['provider_evidence_ids'], [])
        for value in ['0' * 64, None]:
            mutated = copy.deepcopy(self.manifest)
            source = next(s for s in mutated['sources'] if s['id'] == PSAT_SOURCE_ID)
            source['sha256'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'provider evidence'):
                build_guide(mutated, self.registry)

    def test_consortium_developer_role_retains_all_sources_and_exact_scopes(self):
        evidence = load_provider_evidence()
        self.assertEqual(evidence['schema_version'], 1)
        expected = {b['definition']['id'] for b in evidence['bindings']}
        rows = [a for s in self.guide['states'] for a in s['assessments']
                if a['provider'] == 'Smarter Balanced Assessment Consortium']
        self.assertEqual({a['id'] for a in rows}, expected)
        self.assertEqual(len(rows), 9)
        self.assertEqual({a['state'] for a in rows}, {'CA', 'DE', 'NV', 'WA'})
        source_ids = {s['id'] for s in evidence['sources']}
        guide_sources = {s['id']: s for s in self.guide['sources']}
        self.assertEqual(len(guide_sources), len(self.guide['sources']))
        # California is encountered before Michigan. Earlier developer evidence
        # must never displace the independently audited College Board source.
        self.assertEqual(set(guide_sources), source_ids | {PSAT_SOURCE_ID,
            'released-assessment-definitions', '50-state-expansion-registry'})
        for row in rows:
            binding = provider_binding(row, evidence)
            self.assertEqual(row['provider_role'], 'Assessment developer (member-led consortium)')
            self.assertEqual(set(row['provider_evidence_ids']), source_ids)
            self.assertEqual(row['provider_source_url'], guide_sources[binding['primary_source']]['url'])
            self.assertEqual(row['year'], 2025)
            self.assertIsNone(binding['legal_owner'])
            self.assertIsNone(binding['delivery_provider'])
            for source_id in row['provider_evidence_ids']:
                self.assertEqual(guide_sources[source_id]['sha256'],
                                 next(s['sha256'] for s in evidence['sources'] if s['id'] == source_id))

    def test_los_angeles_definitions_have_separate_links_and_explicit_provider_bindings(self):
        rows = self.by_state['CA']['assessments']
        district = [a for a in rows if a['dataset_id'] == 'ca-lausd-2025']
        statewide = {a['level']: a for a in rows if a['dataset_id'] == 'ca-cde-2025'}
        self.assertEqual({a['level'] for a in district}, {'ES', 'HS'})
        for row in district:
            with self.subTest(level=row['level']):
                self.assertEqual([r['id'] for r in row['regions']], ['los-angeles'])
                self.assertEqual([r['id'] for r in statewide[row['level']]['regions']], ['california'])
                for field in ['name', 'year', 'level', 'grades', 'standard', 'source_url']:
                    self.assertEqual(row[field], statewide[row['level']][field])
                self.assertEqual(row['provider'], 'Smarter Balanced Assessment Consortium')
                self.assertEqual(row['provider_role'], 'Assessment developer (member-led consortium)')
                params = parse_qs(urlsplit(row['regions'][0]['url']).query)
                self.assertEqual(params, dict(state=['CA'], region=['los-angeles'], level=[row['level']]))

    def test_miami_dade_definition_has_its_own_native_florida_link_and_population(self):
        rows = self.by_state['FL']['assessments']
        district = [a for a in rows if a['dataset_id'] == 'fl-miami-dade-2025']
        self.assertEqual(len(district), 1)
        row = district[0]
        statewide = next(a for a in rows if a['dataset_id'] == 'fl-schoolgrades-2025')
        for field in ['name', 'year', 'level', 'grades', 'standard', 'source_url']:
            self.assertEqual(row[field], statewide[field])
        self.assertEqual([r['id'] for r in row['regions']], ['miami-dade'])
        self.assertEqual([r['id'] for r in statewide['regions']], ['florida'])
        self.assertEqual(row['level'], 'ES')
        self.assertIsNone(row['provider'])
        self.assertIsNone(row['ambition_comparison'])
        self.assertEqual(parse_qs(urlsplit(row['regions'][0]['url']).query),
                         dict(state=['FL'], region=['miami-dade'], level=['ES']))

    def test_broward_keeps_separate_native_definition_link_and_unverified_provider_roles(self):
        rows = self.by_state['FL']['assessments']
        district = [a for a in rows if a['dataset_id'] == 'fl-broward-2025']
        self.assertEqual(len(district), 1)
        row = district[0]
        statewide = next(a for a in rows if a['dataset_id'] == 'fl-schoolgrades-2025')
        miami = next(a for a in rows if a['dataset_id'] == 'fl-miami-dade-2025')
        for field in ['name', 'year', 'level', 'grades', 'standard', 'source_url']:
            self.assertEqual(row[field], statewide[field])
            self.assertEqual(row[field], miami[field])
        self.assertEqual([r['id'] for r in row['regions']], ['broward'])
        self.assertEqual([r['id'] for r in statewide['regions']], ['florida'])
        self.assertEqual([r['id'] for r in miami['regions']], ['miami-dade'])
        self.assertEqual(parse_qs(urlsplit(row['regions'][0]['url']).query),
                         dict(state=['FL'], region=['broward'], level=['ES']))
        for field in ['provider', 'provider_role', 'provider_source_url', 'ambition_comparison']:
            self.assertIsNone(row[field])
        self.assertEqual(row['provider_evidence_ids'], [])
        self.assertIsNone(provider_binding(row, load_provider_evidence()))
        self.assertIn('1200180', row['regions'][0]['model_scope'])

    def test_orange_definition_preserves_exact_native_population_and_unverified_provider(self):
        rows = self.by_state['FL']['assessments']
        district = [a for a in rows if a['dataset_id'] == 'fl-orange-2025']
        self.assertEqual(len(district), 1)
        row = district[0]
        statewide = next(a for a in rows if a['dataset_id'] == 'fl-schoolgrades-2025')
        for field in ['name', 'year', 'level', 'grades', 'standard', 'source_url']:
            self.assertEqual(row[field], statewide[field])
        self.assertEqual([r['id'] for r in row['regions']], ['orange'])
        self.assertEqual([r['id'] for r in statewide['regions']], ['florida'])
        self.assertEqual(parse_qs(urlsplit(row['regions'][0]['url']).query),
                         dict(state=['FL'], region=['orange'], level=['ES']))
        self.assertIn('1201440', row['regions'][0]['model_scope'])
        for field in ['provider', 'provider_role', 'provider_source_url', 'ambition_comparison']:
            self.assertIsNone(row[field])
        self.assertEqual(row['provider_evidence_ids'], [])
        self.assertIsNone(provider_binding(row, load_provider_evidence()))

    def test_clark_county_has_exact_native_definition_and_explicit_district_provider_binding(self):
        rows = self.by_state['NV']['assessments']
        district = [a for a in rows if a['dataset_id'] == 'nv-clark-county-2025']
        self.assertEqual(len(district), 1)
        row = district[0]
        statewide = next(a for a in rows if a['dataset_id'] == 'nv-edc-ccd-dc')
        for field in ['name', 'year', 'level', 'grades', 'standard', 'source_url']:
            self.assertEqual(row[field], statewide[field])
        self.assertEqual([r['id'] for r in row['regions']], ['clark-county'])
        self.assertEqual([r['id'] for r in statewide['regions']], ['nevada'])
        self.assertEqual(parse_qs(urlsplit(row['regions'][0]['url']).query),
                         dict(state=['NV'], region=['clark-county'], level=['ES']))
        self.assertEqual(row['provider'], 'Smarter Balanced Assessment Consortium')
        self.assertEqual(row['provider_role'], 'Assessment developer (member-led consortium)')
        binding = provider_binding(row, load_provider_evidence())
        self.assertEqual(set(binding['definition']),
                         {'id', 'state', 'name', 'year', 'level', 'grades', 'standard', 'source_url'})
        self.assertIsNone(binding['legal_owner'])
        self.assertIsNone(binding['delivery_provider'])
        self.assertIsNone(row['ambition_comparison'])
        for field in ['standard', 'source_url']:
            changed = dict(row, **{field: 'Changed unaudited native definition'})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'provider definition changed'):
                provider_binding(changed, load_provider_evidence())

    def test_provider_roles_do_not_propagate_from_titles_membership_or_new_years(self):
        evidence = load_provider_evidence()
        definition = copy.deepcopy(next(b['definition'] for b in evidence['bindings']
                                        if b['definition']['level'] == 'ES'))
        for field, value in [('state', 'HI'), ('year', 2026), ('grades', '10'), ('level', 'HS')]:
            changed = dict(definition, **{field: value})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'provider definition changed'):
                provider_binding(changed, evidence)
        # An equally named future definition is not approved by this year audit.
        future = dict(definition, id='ca-cde-2026:2026:Smarter Balanced grades 3–8:ES', year=2026)
        self.assertIsNone(provider_binding(future, evidence))
        for state in ['HI', 'ID', 'OR', 'MI']:
            for row in self.by_state[state]['assessments']:
                if row['dataset_id'] != 'mi-psat8-2025':
                    self.assertIsNone(row['provider'])
        # Delaware's separate SAT row does not inherit the SBAC developer.
        sat = next(a for a in self.by_state['DE']['assessments'] if a['level'] == 'HS')
        self.assertIsNone(sat['provider'])

    def test_changed_provider_extract_requires_a_new_source_audit(self):
        path = ROOT / PROVIDER_EVIDENCE_PATH
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), PROVIDER_EVIDENCE_SHA256)
        with tempfile.TemporaryDirectory() as folder:
            changed = Path(folder) / 'changed.json'
            evidence = json.loads(path.read_text())
            evidence['bindings'][0]['provider_role'] = 'Delivery contractor'
            changed.write_text(json.dumps(evidence))
            with self.assertRaisesRegex(ValueError, 'provider evidence changed'):
                load_provider_evidence(changed)

    def test_only_explicit_test_names_share_smarter_balanced_family(self):
        for state in ['CA', 'DE', 'NV', 'WA']:
            rows = [a for a in self.by_state[state]['assessments']
                    if 'Smarter Balanced' in a['name'] or 'SBAC' in a['name']]
            self.assertTrue(rows)
            self.assertTrue(all(a['family'] == 'Smarter Balanced' for a in rows))
        for state in ['ID', 'OR', 'HI', 'MA', 'RI', 'NJ']:
            self.assertTrue(all(a['family'] != 'Smarter Balanced' for a in self.by_state[state]['assessments']))
        self.assertNotEqual(assessment_family('RICAS grades 3–8'), assessment_family('MCAS grades 3–8'))
        self.assertEqual(assessment_family('ACT (2023-24 levels)'), 'ACT')

    def test_unmatched_or_wrong_region_model_is_rejected(self):
        changed = copy.deepcopy(self.manifest)
        definition = next(a for a in changed['assessments'] if a['id'].startswith('mi-mstep-2025:'))
        definition['name'] = 'Different assessment'
        with self.assertRaisesRegex(ValueError, 'no matching served model'):
            build_guide(changed, self.registry)

    def test_registry_and_repository_path_validation(self):
        for mutate in ['fewer', 'duplicate', 'fips', 'territory']:
            registry = copy.deepcopy(self.registry)
            if mutate == 'fewer':
                registry['states'].pop()
            elif mutate == 'duplicate':
                registry['states'][1]['id'] = registry['states'][0]['id']
            elif mutate == 'fips':
                registry['states'][1]['fips'] = registry['states'][0]['fips']
            else:
                registry['states'][1]['id'] = 'DC'
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                registry_states(registry)
        for value in ['../outside.json', '/private/tmp/outside.json', 'https://example.com/data.json', 'data/file.json?x=1']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                local_path(ROOT, value)

    def test_boundary_identity_island_retention_winding_and_reproducibility(self):
        validate_boundaries(self.geometry, self.registry)
        rebuilt = extract_boundaries(self.registry)
        self.assertEqual(rebuilt, self.geometry)
        self.assertEqual(rebuilt['sources'][0]['sha256'], BOUNDARY_SHA256)
        self.assertLess(rebuilt['simplification']['served_points'], rebuilt['simplification']['native_points'])
        states = {f['id']: f for f in self.geometry['features']}
        self.assertEqual(len(states), 50)
        self.assertTrue(all(f['geometry']['coordinates'] for f in states.values()))
        alaska = [p for poly in states['AK']['geometry']['coordinates'] for p in poly[0]]
        hawaii = [p for poly in states['HI']['geometry']['coordinates'] for p in poly[0]]
        self.assertTrue(any(lon > 170 for lon, lat in alaska))  # Western Aleutians retained.
        self.assertTrue(any(lat > 70 for lon, lat in alaska))
        self.assertTrue(all(-180 < lon < -154 and 18 < lat < 30 for lon, lat in hawaii))
        self.assertGreater(len(states['HI']['geometry']['coordinates']), 5)
        self.assertGreater(len(states['AK']['geometry']['coordinates']), 100)
        self.assertNotIn('DC', states)
        self.assertNotIn('PR', states)

    def test_boundary_corruption_or_new_source_requires_review(self):
        for mutate in ['missing', 'identity', 'winding', 'source', 'duplicate']:
            geometry = copy.deepcopy(self.geometry)
            feature = geometry['features'][0]
            if mutate == 'missing':
                geometry['features'].pop()
            elif mutate == 'identity':
                feature['properties']['STUSPS'] = 'XX'
            elif mutate == 'winding':
                feature['geometry']['coordinates'][0][0].reverse()
            elif mutate == 'source':
                geometry['sources'][0]['sha256'] = '0' * 64
            else:
                geometry['features'][1] = copy.deepcopy(feature)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate_boundaries(geometry, self.registry)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'changed.zip'
            path.write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError, 'source audit'):
                extract_boundaries(self.registry, path)

    def test_simplification_keeps_small_islands_and_closed_d3_exteriors(self):
        tiny = [[0, 0], [0, .0001], [.0001, .0001], [.0001, 0], [0, 0]]
        self.assertEqual(simplify_ring(tiny), tiny)
        line = [[i / 100, 0] for i in range(101)]
        self.assertEqual(simplify_line(line, .008), [[0, 0], [1, 0]])
        rectangle = ([[0, i / 100] for i in range(101)]
                     + [[i / 100, 1] for i in range(1, 101)]
                     + [[1, 1 - i / 100] for i in range(1, 101)]
                     + [[1 - i / 100, 0] for i in range(1, 101)])
        result = simplify_ring(rectangle)
        self.assertEqual(result[0], result[-1])
        self.assertLess(len(result), len(rectangle))
        self.assertLess(signed_area(result), 0)
        self.assertAlmostEqual(abs(signed_area(result)), 1)
        self.assertEqual(simplify_ring(list(reversed(tiny))), tiny)
        with self.assertRaises(ValueError):
            simplify_ring([[0, 0], [1, 1], [2, 2], [0, 0]])


if __name__ == '__main__':
    unittest.main()
