const {test} = require('node:test');
const assert = require('node:assert/strict');
const {guideFilters, guideRows, guideURL} = require('../assessments.js');
const guide = {states: [
  {id: 'CA', assessments: [{family: 'Smarter Balanced', level: 'ES'}, {family: 'Smarter Balanced', level: 'HS'}]},
  {id: 'MI', assessments: [{family: 'M-STEP', level: 'ES'}, {family: 'PSAT 8/9', level: 'ES'}]},
  {id: 'NH', assessments: []}
]};
test('invalid share filters safely restore grade-school defaults', () => {
  assert.deepEqual(guideFilters(new URLSearchParams('state=DC&test=unknown&level=bad'), guide), {state:'all', test:'all', level:'ES'});
});
test('valid combinations preserve a state that has no matching test', () => {
  const filters = guideFilters(new URLSearchParams('state=NH&test=Smarter+Balanced&level=HS'), guide);
  assert.deepEqual(filters, {state:'NH', test:'Smarter Balanced', level:'HS'});
  assert.deepEqual(guideRows(guide, filters), []);
});
test('unknown-state metadata remains available under the all-test filter', () => {
  assert.deepEqual(guideRows(guide, {state:'NH', test:'all', level:'ES'}).map(row => row.id), ['NH']);
});
test('shared-test and population filters do not include other families', () => {
  const rows = guideRows(guide, {state:'all', test:'Smarter Balanced', level:'HS'});
  assert.equal(rows.length, 1);
  assert.equal(rows[0].id, 'CA');
  assert.deepEqual(rows[0].assessments, [{family:'Smarter Balanced', level:'HS'}]);
  assert.equal(guide.states[0].assessments.length, 2);
});
test('all-population URL and punctuation round-trip under project hosting', () => {
  const filters = {state:'MI', test:'PSAT 8/9', level:'all'};
  const url = guideURL('https://example.org/FRPL-RMA/assessments.html?keep=yes#assessment-workspace', filters);
  assert.equal(url.pathname, '/FRPL-RMA/assessments.html');
  assert.equal(url.searchParams.get('keep'), 'yes');
  assert.equal(url.hash, '#assessment-workspace');
  assert.deepEqual(guideFilters(url.searchParams, guide), filters);
});
test('reset removes owned defaults while preserving unrelated parameters', () => {
  const url = guideURL('https://example.org/FRPL-RMA/assessments.html?state=MI&test=PSAT&level=HS&keep=yes', {state:'all', test:'all', level:'ES'});
  assert.equal(url.search, '?keep=yes');
});
