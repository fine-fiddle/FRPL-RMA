'use strict';

function guideFilters(params, guide) {
  const stateIDs = new Set(guide.states.map(state => state.id));
  const families = new Set(guide.states.flatMap(state => state.assessments.map(row => row.family)));
  return {
    state: stateIDs.has(params.get('state')) ? params.get('state') : 'all',
    test: families.has(params.get('test')) ? params.get('test') : 'all',
    level: ['ES', 'HS', 'all'].includes(params.get('level')) ? params.get('level') : 'ES'
  };
}

function guideRows(guide, filters) {
  return guide.states.filter(state => filters.state === 'all' || filters.state === state.id).map(state => ({
    ...state,
    assessments: state.assessments.filter(row => (filters.level === 'all' || row.level === filters.level)
      && (filters.test === 'all' || row.family === filters.test))
  })).filter(state => state.assessments.length || filters.test === 'all');
}

function guideURL(current, filters) {
  const url = new URL(current);
  for (const key of ['state', 'test', 'level']) {
    const value = filters[key];
    if (value === 'all' && key !== 'level' || key === 'level' && value === 'ES') url.searchParams.delete(key);
    else url.searchParams.set(key, value);
  }
  return url;
}

async function initAssessmentGuide() {
  const $ = selector => document.querySelector(selector);
  const node = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const link = (label, href) => {
    const element = node('a', label);
    element.href = href;
    return element;
  };
  try {
    const [guide, boundaries] = await Promise.all(['data/assessment-guide.json', 'data/us-states.geojson'].map(async path => {
      const response = await fetch(path);
      if (!response.ok) throw new Error(`Could not load ${path}`);
      return response.json();
    }));
    let filters = guideFilters(new URL(window.location.href).searchParams, guide);
    const states = [...guide.states].sort((a, b) => a.name.localeCompare(b.name));
    const families = [...new Set(states.flatMap(state => state.assessments.map(row => row.family)))].sort();
    for (const state of states) $('#guide-state').append(new Option(state.name, state.id));
    for (const family of families) $('#guide-test').append(new Option(family, family));
    const color = d3.scaleOrdinal(families, families.map((_, index) => d3.interpolateRainbow((index + .5) / families.length)));
    const svg = d3.select('#assessment-map svg');
    const defs = svg.append('defs');
    const pattern = defs.append('pattern').attr('id', 'multiple-tests').attr('width', 7).attr('height', 7).attr('patternUnits', 'userSpaceOnUse').attr('patternTransform', 'rotate(35)');
    pattern.append('rect').attr('width', 7).attr('height', 7).attr('fill', '#e0e7ef');
    pattern.append('rect').attr('width', 3).attr('height', 7).attr('fill', '#7b8da5');
    const projection = d3.geoAlbersUsa().fitExtent([[12, 18], [948, 588]], boundaries);
    const path = d3.geoPath(projection);
    const mapStates = svg.append('g').selectAll('path').data(boundaries.features).join('path')
      .attr('class', 'assessment-state').attr('d', path).attr('tabindex', 0).attr('role', 'button');
    mapStates.append('title');
    const legend = $('#assessment-legend');
    const legendButtons = new Map();
    for (const family of families) {
      const button = node('button', undefined, 'family-key');
      button.type = 'button';
      const swatch = node('span', undefined, 'family-swatch');
      swatch.style.background = color(family);
      swatch.setAttribute('aria-hidden', 'true');
      button.append(swatch, node('span', family));
      button.addEventListener('click', () => {
        filters.test = filters.test === family ? 'all' : family;
        render();
      });
      legendButtons.set(family, button);
      legend.append(button);
    }

    function selectState(feature) {
      const id = feature.properties.id;
      filters.state = filters.state === id ? 'all' : id;
      render();
    }
    mapStates.on('click', (_, feature) => selectState(feature)).on('keydown', (event, feature) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectState(feature);
      }
    });

    function stateDescription(feature) {
      const state = states.find(item => item.id === feature.properties.id);
      const rows = state.assessments.filter(row => filters.level === 'all' || row.level === filters.level);
      const names = [...new Set(rows.map(row => row.family))];
      return `${state.name}: ${names.length ? names.join('; ') : 'no released metadata for this population'}`;
    }
    mapStates.on('focus mouseenter', (_, feature) => { $('#map-focus').textContent = stateDescription(feature); });

    function render() {
      for (const key of ['state', 'test', 'level']) $(`#guide-${key}`).value = filters[key];
      window.history.replaceState(null, '', guideURL(window.location.href, filters));
      const visible = guideRows(guide, filters);
      const rowCount = visible.reduce((total, state) => total + state.assessments.length, 0);
      const withRows = visible.filter(state => state.assessments.length).length;
      const unavailable = visible.length - withRows;
      $('#guide-count').textContent = `${rowCount} assessment definition${rowCount === 1 ? '' : 's'} across ${withRows} state${withRows === 1 ? '' : 's'} · ${unavailable} state${unavailable === 1 ? '' : 's'} without released metadata for these filters`;
      const list = $('#assessment-list');
      list.replaceChildren();
      if (!visible.length) {
        const empty = node('div', undefined, 'panel assessment-empty');
        empty.append(node('h2', 'No matching assessments'), node('p', 'Try another state, test family or comparison population.'));
        const reset = node('button', 'Reset filters', 'text-button');
        reset.type = 'button';
        reset.addEventListener('click', resetFilters);
        empty.append(reset);
        list.append(empty);
      }
      for (const state of visible) {
        const card = node('article', undefined, 'panel assessment-state-card');
        const heading = node('div', undefined, 'assessment-state-heading');
        heading.append(node('h2', state.name), link('State source audit', state.guide));
        card.append(heading);
        if (!state.assessments.length) {
          const message = state.assessments.length === 0 && !guide.states.find(item => item.id === state.id).assessments.length
            ? 'Assessment metadata is awaiting the state source audit.' : 'No released assessment metadata for this comparison population.';
          card.append(node('p', message, 'assessment-hold'));
          if (state.blocker_summary) card.append(node('p', state.blocker_summary, 'assessment-hold'));
        }
        for (const assessment of state.assessments) {
          const row = node('section', undefined, 'assessment-row');
          row.append(node('h3', assessment.name));
          const meta = node('div', undefined, 'assessment-meta');
          meta.append(node('span', `${assessment.year - 1}–${String(assessment.year).slice(-2)}`), node('span', assessment.family));
          row.append(meta);
          const dl = node('dl');
          dl.append(node('dt', 'Tested grades'), node('dd', assessment.grades), node('dt', 'Owner / provider'));
          const provider = node('dd');
          if (assessment.provider && assessment.provider_source_url) {
            provider.append(link(assessment.provider, assessment.provider_source_url));
            if (assessment.provider_role) provider.append(document.createTextNode(` · ${assessment.provider_role}`));
          } else provider.textContent = 'Not yet audited';
          dl.append(provider, node('dt', 'Relative target'), node('dd', 'Not yet audited'));
          row.append(dl);
          const details = node('details');
          details.append(node('summary', 'Proficiency definition & sources'), node('p', assessment.standard, 'assessment-definition'));
          if (assessment.source_url) details.append(link('Published assessment source', assessment.source_url));
          row.append(details);
          const links = node('div', undefined, 'assessment-links');
          for (const region of assessment.regions) links.append(link(`${region.name} comparison ↗`, region.url));
          row.append(links);
          card.append(row);
        }
        list.append(card);
      }
      const familiesFor = feature => {
        const state = states.find(item => item.id === feature.properties.id);
        return [...new Set(state.assessments.filter(row => filters.level === 'all' || row.level === filters.level).map(row => row.family))];
      };
      mapStates.attr('fill', feature => {
        const names = familiesFor(feature);
        return names.length > 1 ? 'url(#multiple-tests)' : names.length ? color(names[0]) : '#c7d0dd';
      }).attr('opacity', feature => {
        const stateMatch = filters.state === 'all' || filters.state === feature.properties.id;
        const testMatch = filters.test === 'all' || familiesFor(feature).includes(filters.test);
        return stateMatch && testMatch ? 1 : .25;
      }).attr('aria-pressed', feature => String(filters.state === feature.properties.id))
        .attr('aria-label', feature => `${stateDescription(feature)}. Select state.`)
        .select('title').text(stateDescription);
      for (const [family, button] of legendButtons) button.setAttribute('aria-pressed', String(filters.test === family));
      $('#map-focus').textContent = filters.state === 'all' ? 'All 50 states remain on the map.' : `${states.find(state => state.id === filters.state).name} selected.`;
    }
    function resetFilters() {
      filters = {state: 'all', test: 'all', level: 'ES'};
      render();
    }
    for (const key of ['state', 'test', 'level']) $(`#guide-${key}`).addEventListener('change', event => {
      filters[key] = event.target.value;
      render();
    });
    $('#guide-reset').addEventListener('click', resetFilters);
    window.addEventListener('popstate', () => {
      filters = guideFilters(new URL(window.location.href).searchParams, guide);
      render();
    });
    render();
  } catch (error) {
    $('#guide-error').hidden = false;
    $('#guide-count').textContent = 'Assessment guide unavailable.';
    console.error(error);
  }
}

if (typeof module !== 'undefined' && module.exports) module.exports = {guideFilters, guideRows, guideURL};
if (typeof document !== 'undefined') initAssessmentGuide();
