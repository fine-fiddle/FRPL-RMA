'use strict';
const $ = selector => document.querySelector(selector);
const state = { level: 'ES', subject: 'combined', program: 'all', query: '', selected: new Set(), focus: null, scope: 'selected' };
let data, geography, mapZoom, mapSvg;
const LIST_PAGE_SIZE = 75;
let listLimit = LIST_PAGE_SIZE, searchTimer;
function syncURL() {
  const url = new URL(window.location.href);
  const params = url.searchParams;
  params.set('state', $('#state-select').value);
  params.set('region', $('#region-select').value);
  params.set('level', state.level);
  params.set('subject', state.subject === 'reading' ? 'ela' : state.subject);
  params.set('program', state.program);
  if (state.query) params.set('q', state.query); else params.delete('q');
  // An explicit empty value distinguishes no selection from the default schools.
  params.set('schools', [...state.selected].join(','));
  if (state.focus) params.set('focus', state.focus); else params.delete('focus');
  params.set('scope', state.scope);
  if (url.href !== window.location.href) window.history.replaceState(null, '', url);
}
function restoreURL(params, statewide) {
  state.level = ['ES','HS'].includes(params.get('level')) ? params.get('level') : 'ES';
  const subject = params.get('subject') === 'ela' ? 'reading' : params.get('subject');
  state.subject = ['math','reading','combined'].includes(subject) ? subject : 'combined';
  const programs = [...$('#program').options].map(o=>o.value);
  state.program = !statewide && programs.includes(params.get('program')) ? params.get('program') : 'all';
  state.query = (params.get('q') || '').trim().toLowerCase();
  state.scope = params.get('scope') === 'filtered' ? 'filtered' : 'selected';
  defaults();
  const ids = new Set(cohort().map(s=>s.id));
  if (params.has('schools')) state.selected = new Set((params.get('schools') || '').split(',').filter(id=>ids.has(id)).slice(0,6));
  if (ids.has(params.get('focus'))) state.focus = params.get('focus');
  else { state.focus = [...state.selected][0] || null; if (!state.focus) ensureFocus(); }
  $('#level').value = state.level;
  $('#search').value = state.query;
  $('#program').value = state.program;
  $('#scope').value = state.scope;
  document.querySelectorAll('[data-subject]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.subject===state.subject));
}
const color = { above: '#14816f', below: '#c76753', focus: '#315bda', gray: '#a9b5c8', ink: '#182840' };
const signed = (n, digits = 2) => n == null ? 'Unavailable' : `${n > 0 ? '+' : ''}${n.toFixed(digits)}`;
const testedLabel = n => n == null ? 'Tested count unavailable' : `${n.toLocaleString()} tested`;
const hasInterval = m => m && Number.isFinite(m.low) && Number.isFinite(m.high);
const intervalLabel = m => hasInterval(m) ? `${signed(m.low)} to ${signed(m.high)}` : 'Sampling interval unavailable';
const pct = n => n == null ? 'Unavailable' : `${n.toFixed(1)}%`;
const subjectLabel = () => ({ math: 'Math', reading: 'ELA', combined: 'Combined' })[state.subject];
const metric = s => s.metrics[state.subject];
const escapeHTML = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const schoolById = id => data.schools.find(s => s.id === id);
const cohort = () => data.schools.filter(s => s.level === state.level);
const filtered = () => cohort().filter(s => (state.program === 'all' || s.program === state.program) && `${s.name} ${s.short} ${s.district || ''} ${s.city || ''} ${s.county || ''}`.toLowerCase().includes(state.query));
const model = () => data.models[state.level][state.subject];
const announce = message => { $('#status').textContent = message; };
const displayName = s => s.short.replace(/\bHS\b/g, 'High School').replace(/\bES\b/g, 'Elementary').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
function tooltip(event, s) {
  const m = metric(s);
  const tip = $('#tooltip');
  tip.innerHTML = `<strong>${escapeHTML(s.name)}</strong>${escapeHTML(s.district || s.program)} · Low income ${pct(s.income)}<br>${m ? `Proficiency ${pct(m.actual)} · Residual ${signed(m.studentized)}<br>${testedLabel(m.tested)} · ${intervalLabel(m)}${state.subject === 'combined' ? ' (smaller subject count)' : ''}` : 'Comparable assessment data unavailable'}`;
  tip.hidden = false;
  const box = event.currentTarget.getBoundingClientRect();
  const x = event.clientX || box.x + box.width / 2, y = event.clientY || box.y;
  tip.style.left = `${Math.max(8, Math.min(x + 12, window.innerWidth - 280))}px`;
  tip.style.top = `${Math.max(8, Math.min(y + 14, window.innerHeight - 130))}px`;
}
function hideTooltip() { $('#tooltip').hidden = true; }
function inspect(id, add = false) {
  state.focus = id;
  if (add && metric(schoolById(id)) && state.selected.size < 6) state.selected.add(id);
  render();
}
function choose(id, checked) {
  if (checked && state.selected.size >= 6) { announce('Six schools selected. Remove one to add another.'); renderList(); return; }
  checked ? state.selected.add(id) : state.selected.delete(id);
  if (checked) state.focus = id;
  render();
  announce(`${state.selected.size} schools selected.`);
}
function defaults() {
  state.selected.clear();
  const names = state.level === 'ES' ? ['BELL', 'BURLEY', 'SKINNER NORTH'] : ['PAYTON HS', 'LINCOLN PARK HS', 'LAKE VIEW HS'];
  names.forEach(n => { const s = cohort().find(s => s.short === n && metric(s)); if (s) state.selected.add(s.id); });
  state.focus = [...state.selected][0] || cohort().find(s => metric(s))?.id;
  if (!state.selected.size && state.focus) state.selected.add(state.focus);
}
function ensureFocus() {
  const rows = filtered();
  if (!rows.some(s => s.id === state.focus)) state.focus = rows.find(s => metric(s))?.id || rows[0]?.id || null;
}
function renderList() {
  const rows = filtered().sort((a,b) => a.short.localeCompare(b.short));
  $('#school-count').textContent = `${rows.length} schools · ${rows.filter(s => metric(s)).length} with data`;
  const list = $('#school-list');
  list.innerHTML = rows.length ? '' : '<p class="empty">No schools match these filters. Try another name or school type.</p>';
  const fragment = document.createDocumentFragment();
  for (const s of rows.slice(0, listLimit)) {
    const m = metric(s), row = document.createElement('div');
    row.className = `school-row${state.focus === s.id ? ' focused' : ''}`;
    row.innerHTML = `<input id="compare-${s.id}" type="checkbox" aria-label="Compare ${escapeHTML(s.name)}" ${state.selected.has(s.id) ? 'checked' : ''} ${m ? '' : 'disabled'}><button id="inspect-${s.id}" class="school-name" title="${escapeHTML(s.name)}">${escapeHTML(displayName(s))}<small>${escapeHTML(s.city ? `${s.city} · ${s.district}` : s.program)} · ${s.income == null ? 'Income unavailable' : `${pct(s.income)} low income`}</small></button><span class="residual-value ${m && m.studentized >= 0 ? 'positive-text' : 'negative-text'}">${m ? signed(m.studentized) : '—'}</span>`;
    row.querySelector('input').addEventListener('change', e => choose(s.id, e.target.checked));
    row.querySelector('button').addEventListener('click', () => inspect(s.id));
    fragment.append(row);
  }
  list.append(fragment);
  if (rows.length > listLimit) {
    const more = document.createElement('button');
    more.id = 'more-schools';
    more.className = 'more-schools';
    more.textContent = `Show next ${Math.min(LIST_PAGE_SIZE, rows.length-listLimit)} schools (${listLimit} of ${rows.length} shown)`;
    more.addEventListener('click', () => {
      const firstNewId = rows[listLimit].id;
      listLimit += LIST_PAGE_SIZE;
      renderList();
      document.getElementById(`inspect-${firstNewId}`)?.focus({preventScroll:true});
    });
    list.append(more);
  }
}
function renderMap() {
  const host = $('#map'), width = host.clientWidth, height = host.clientHeight;
  const previous = mapSvg ? d3.zoomTransform(mapSvg.node()) : d3.zoomIdentity;
  host.replaceChildren();
  if (!geography) {
    mapSvg = null;
    host.innerHTML = '<p class="empty">Statewide map coordinates are not available yet. Use the searchable school list to explore Illinois rankings.</p>';
    return;
  }
  mapSvg = d3.select(host).append('svg').attr('viewBox', `0 0 ${width} ${height}`).attr('role', 'img').attr('aria-label','Map of matching schools. Choose a marker to inspect it. The school list provides a keyboard-accessible alternative.');
  const projection = d3.geoMercator().fitExtent([[20,12],[width - 35,height-12]], geography);
  const layer = mapSvg.append('g');
  layer.selectAll('path').data(geography.features).join('path').attr('d',d3.geoPath(projection)).attr('fill','#e1e7eb').attr('stroke','#fafcfd').attr('stroke-width',.65);
  const lake = projection([-87.555,41.90]);
  layer.append('text').attr('x',lake[0]).attr('y',lake[1]).attr('fill','#9bacb7').attr('font-size',12).attr('font-style','italic').attr('transform',`rotate(-65 ${lake[0]} ${lake[1]})`).text('Lake Michigan');
  const rows = filtered().filter(s => s.latitude != null && s.longitude != null).sort((a,b) => Number(state.selected.has(a.id))-Number(state.selected.has(b.id)));
  layer.selectAll('circle').data(rows).join('circle').attr('class','chart-point').attr('cx',s=>projection([s.longitude,s.latitude])[0]).attr('cy',s=>projection([s.longitude,s.latitude])[1]).attr('r',s=>state.focus===s.id?6:state.selected.has(s.id)?4.7:2.8).attr('fill',s=>state.focus===s.id?color.focus:metric(s)?metric(s).studentized>=0?color.above:color.below:color.gray).attr('fill-opacity',s=>state.selected.has(s.id)?1:.65).attr('stroke',s=>state.selected.has(s.id)?'#fff':'none').attr('stroke-width',1.5).on('mouseenter',tooltip).on('mousemove',tooltip).on('mouseleave',hideTooltip).on('click',(e,s)=>{hideTooltip();inspect(s.id,true);}).append('title').text(s=>s.name);
  mapZoom = d3.zoom().scaleExtent([1,9]).translateExtent([[-width,-height],[width*2,height*2]]).on('zoom',e=>{layer.attr('transform',e.transform);layer.selectAll('circle').attr('stroke-width',1.5/e.transform.k);});
  mapSvg.call(mapZoom).call(mapZoom.transform,previous);
  mapSvg.append('text').attr('x',15).attr('y',25).attr('font-size',12).attr('fill','#667386').text('N ↑');
  if (!rows.length) mapSvg.append('text').attr('x',width/2).attr('y',height/2).attr('text-anchor','middle').attr('font-size',13).attr('fill',color.ink).text('No schools match');
}
function renderScatter() {
  const host = $('#scatter'); host.replaceChildren();
  const width=host.clientWidth-18, height=host.clientHeight, margin={left:44,right:17,top:22,bottom:45};
  const rows=cohort().filter(s=>metric(s));
  const m=model(), selected=schoolById(state.focus), sm=selected && metric(selected);
  const predictions=[m.intercept,m.intercept+100*m.slope];
  const x=d3.scaleLinear().domain([0,100]).range([margin.left,width-margin.right]);
  const y=d3.scaleLinear().domain([Math.min(0,...predictions)-2,Math.max(100,...predictions)+2]).range([height-margin.bottom,margin.top]);
  const svg=d3.select(host).append('svg').attr('viewBox',`0 0 ${width} ${height}`).attr('role','img').attr('aria-label',`${subjectLabel()} proficiency versus low-income enrollment; regression slope ${m.slope.toFixed(2)}. ${sm?`${selected.name}: actual ${pct(sm.actual)}, predicted ${pct(sm.predicted)}, residual ${signed(sm.residual,1)} percentage points.`:''}`);
  svg.append('g').attr('class','axis').attr('transform',`translate(${margin.left},0)`).call(d3.axisLeft(y).tickValues([0,25,50,75,100]).tickFormat(d=>`${d}%`).tickSize(-(width-margin.left-margin.right))).call(g=>g.select('.domain').remove());
  svg.append('g').attr('class','axis').attr('transform',`translate(0,${height-margin.bottom})`).call(d3.axisBottom(x).ticks(5).tickFormat(d=>`${d}%`).tickSize(0)).call(g=>g.selectAll('text').attr('dy',16));
  svg.append('text').attr('x',margin.left).attr('y',11).attr('font-size',12).attr('fill','#667386').text(`${state.subject==='combined'?'Mean':state.subject==='reading'?'ELA':'Math'} proficiency`);
  svg.append('text').attr('x',(width+margin.left)/2).attr('y',height-7).attr('text-anchor','middle').attr('font-size',12).attr('fill','#667386').text('Economic disadvantage (% low income)');
  const matching=new Set(filtered().map(s=>s.id));
  svg.append('g').selectAll('circle').data(rows).join('circle').attr('class','chart-point').attr('cx',s=>x(s.income)).attr('cy',s=>y(metric(s).actual)).attr('r',s=>state.selected.has(s.id)?4:2.5).attr('fill',s=>state.selected.has(s.id)?color.focus:color.gray).attr('opacity',s=>matching.has(s.id)?.55:.12).on('mouseenter',tooltip).on('mouseleave',hideTooltip).on('click',(e,s)=>{hideTooltip();inspect(s.id,true);});
  svg.append('line').attr('x1',x(0)).attr('x2',x(100)).attr('y1',y(predictions[0])).attr('y2',y(predictions[1])).attr('stroke',color.ink).attr('stroke-width',1.8);
  if(sm){
    const xx=x(selected.income), ya=y(sm.actual), yp=y(sm.predicted);
    svg.append('line').attr('x1',xx).attr('x2',xx).attr('y1',ya).attr('y2',yp).attr('stroke',color.focus).attr('stroke-width',2).attr('stroke-dasharray','4 3');
    svg.append('circle').attr('cx',xx).attr('cy',yp).attr('r',4.5).attr('fill','white').attr('stroke',color.focus).attr('stroke-width',2);
    svg.append('circle').attr('cx',xx).attr('cy',ya).attr('r',6).attr('fill',color.focus).attr('stroke','white').attr('stroke-width',2);
    const right=xx<width*.65;
    svg.append('text').attr('x',xx+(right?10:-10)).attr('y',(ya+yp)/2+3).attr('text-anchor',right?'start':'end').attr('font-size',12).attr('font-weight',700).attr('fill',color.focus).attr('paint-order','stroke').attr('stroke','white').attr('stroke-width',3).text(`ε ${signed(sm.residual,1)} pp`);
    $('#focus-summary').innerHTML=`<strong>${escapeHTML(displayName(selected))} <span style="font-weight:400">· focus school</span></strong><div class="focus-stats"><div><span>Actual</span><b>${pct(sm.actual)}</b></div><div><span>Predicted</span><b>${pct(sm.predicted)}</b></div><div class="gap-value"><span>Difference · ε</span><b style="color:${sm.residual>=0?color.above:color.below}">${signed(sm.residual,1)} <small>pp</small></b></div></div>`;
  }else $('#focus-summary').innerHTML=`<p>${selected?escapeHTML(displayName(selected))+' has no comparable data for this subject.':'Choose a school to see actual and predicted proficiency.'}</p>`;
  $('#model-size').textContent=`${m.n} SCHOOLS`;
}
function renderHistory() {
  const host = $('#history-chart');
  host.replaceChildren();
  const school = schoolById(state.focus);
  const history = school?.history || [];
  const label = state.subject === 'reading' ? 'ELA' : state.subject === 'combined' ? 'Combined' : 'Math';
  $('#history-subtitle').textContent = school ? `${displayName(school)} · ${label} studentized residual` : 'Select a school to see its residual history.';
  $('#history-table').replaceChildren();
  if (!history.length) {
    $('#history-years').textContent = '';
    host.innerHTML = '<p class="empty">No historical assessment record is available for this school.</p>';
    return;
  }
  const values = history.map(r => ({...r, ...r.subjects[state.subject], value: r.subjects[state.subject]?.studentized})).filter(r => Number.isFinite(r.value));
  $('#history-years').textContent = values.length ? `${values.length} ${values.length === 1 ? 'YEAR · SNAPSHOT ONLY' : 'YEARS'}` : '';
  if (!values.length) {
    host.innerHTML = `<p class="empty">No ${label.toLowerCase()} residual history is available. Each point requires an eligible assessment and matching same-year income data.</p>`;
    return;
  }
  const width = Math.max(host.clientWidth - 20, 300), height = 280;
  const margin = {left: 46, right: 22, top: 20, bottom: 48};
  const historyYears = data.history_years || [2015,2016,2017,2018,2019,2021,2022,2023,2024];
  const firstYear = Math.min(...historyYears), lastYear = Math.max(...historyYears);
  const x = d3.scaleLinear().domain(firstYear === lastYear ? [firstYear-.5,lastYear+.5] : [firstYear,lastYear]).range([margin.left, width - margin.right]);
  const extent = Math.max(2, ...values.flatMap(d=>[Math.abs(d.value),Math.abs(d.low || 0),Math.abs(d.high || 0)]));
  const y = d3.scaleLinear().domain([-extent, extent]).nice().range([height - margin.bottom, margin.top]);
  const svg = d3.select(host).append('svg').attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`).attr('role', 'img')
    .attr('aria-label', `${displayName(school)} ${label} externally studentized residuals from ${values[0].year} to ${values[values.length - 1].year}. Zero is predicted performance. Bars show approximate 95% sampling intervals. Values are in the table below.`);
  svg.append('g').attr('class','axis').attr('transform',`translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(d=>signed(d,1)).tickSize(-(width-margin.left-margin.right))).call(g=>g.select('.domain').remove());
  svg.append('g').attr('class','axis').attr('transform',`translate(0,${height-margin.bottom})`).call(d3.axisBottom(x).tickValues(d3.range(firstYear,lastYear+1)).tickFormat(d=>d).tickSize(0)).call(g=>g.selectAll('text').attr('dy',16).attr('transform','rotate(-35)').style('text-anchor','end'));
  svg.append('text').attr('x',margin.left).attr('y',11).attr('font-size',11).attr('fill','#667386').text('Studentized residual · above / below prediction');
  svg.append('line').attr('x1',margin.left).attr('x2',width-margin.right).attr('y1',y(0)).attr('y2',y(0)).attr('stroke',color.ink).attr('stroke-width',1.5);
  if (firstYear <= 2020 && lastYear >= 2020) {
    svg.append('line').attr('x1',x(2020)).attr('x2',x(2020)).attr('y1',margin.top).attr('y2',height-margin.bottom).attr('stroke','#c8d1dc').attr('stroke-dasharray','3 3');
    svg.append('text').attr('x',x(2020)+6).attr('y',margin.top+12).attr('font-size',10).attr('fill','#667386').text('2020 no test');
  }
  const pointColor = d=>d.value>=0?color.above:color.below;
  // Connect only adjacent years using the same assessment; preserve missing-year gaps.
  const segments = values.slice(1).map((d,i)=>[values[i],d]).filter(([a,b])=>b.year===a.year+1 && a.assessment===b.assessment);
  svg.append('g').selectAll('line').data(segments).join('line').attr('x1',d=>x(d[0].year)).attr('x2',d=>x(d[1].year)).attr('y1',d=>y(d[0].value)).attr('y2',d=>y(d[1].value)).attr('stroke',color.focus).attr('stroke-width',2);
  svg.append('g').selectAll('line').data(values.filter(hasInterval)).join('line').attr('x1',d=>x(d.year)).attr('x2',d=>x(d.year)).attr('y1',d=>y(d.low)).attr('y2',d=>y(d.high)).attr('stroke',pointColor).attr('stroke-width',2).attr('opacity',.7);
  for (const end of ['low','high']) svg.append('g').selectAll('line').data(values.filter(hasInterval)).join('line').attr('x1',d=>x(d.year)-4).attr('x2',d=>x(d.year)+4).attr('y1',d=>y(d[end])).attr('y2',d=>y(d[end])).attr('stroke',pointColor);
  const description = d=>`${d.year} ${d.assessment}: actual ${pct(d.actual)}, predicted ${pct(d.predicted)}, difference ${signed(d.residual,1)} pp; studentized residual ${signed(d.value)}, ${intervalLabel(d)}; low income ${pct(d.income)}; ${testedLabel(d.tested)}; ${d.cohort_n} schools in model`;
  const points = svg.append('g').selectAll('circle').data(values).join('circle').attr('class','history-point').attr('cx',d=>x(d.year)).attr('cy',d=>y(d.value)).attr('r',5).attr('fill',pointColor).attr('stroke','white').attr('stroke-width',2).attr('tabindex',0).attr('aria-label',description);
  points.append('title').text(description);
  function showHistoryPoint(e,d) {
    const tip=$('#tooltip'); tip.textContent=description(d); tip.hidden=false;
    const box=e.currentTarget.getBoundingClientRect();
    tip.style.left=`${Math.max(8,Math.min(box.x+12,window.innerWidth-280))}px`;
    tip.style.top=`${Math.max(8,Math.min(box.y+14,window.innerHeight-tip.offsetHeight-8))}px`;
  }
  points.on('mouseenter',showHistoryPoint).on('focus',showHistoryPoint).on('mouseleave',hideTooltip).on('blur',hideTooltip).on('keydown',e=>{if(e.key==='Escape')hideTooltip();});
  svg.append('text').attr('x',width-margin.right).attr('y',height-7).attr('text-anchor','end').attr('font-size',10).attr('fill','#667386').text('School year');
  const assessments = [...new Set(values.map(d=>d.assessment))];
  $('#history-subtitle').textContent = `${displayName(school)} · ${label} residuals · ${assessments.join(' → ')}${values.some(d=>!hasInterval(d)) ? ' · Sampling intervals unavailable for points without bars' : ''}`;
  $('#history-table').innerHTML = `<table><caption>${escapeHTML(displayName(school))} · ${label}: annual actual versus predicted</caption><thead><tr><th>Year / test</th><th>Low income</th><th>Actual</th><th>Predicted</th><th>Difference</th><th>Studentized residual</th><th>95% interval</th><th>Tested</th><th>Model schools</th></tr></thead><tbody>${history.map(r=>{const m=r.subjects[state.subject]; return m ? `<tr><th>${r.year} ${escapeHTML(r.assessment)}</th><td>${pct(r.income)}</td><td>${pct(m.actual)}</td><td>${pct(m.predicted)}</td><td>${signed(m.residual,1)} pp</td><td>${signed(m.studentized)}</td><td>${intervalLabel(m)}</td><td>${m.tested == null ? 'Unavailable' : m.tested.toLocaleString()}</td><td>${m.cohort_n}</td></tr>` : `<tr><th>${r.year} ${escapeHTML(r.assessment)}</th><td>${pct(r.income)}</td><td colspan="7">${escapeHTML(r.exclusions[state.subject] || 'No eligible result')}</td></tr>`;}).join('')}</tbody></table>`;
}
function renderComparison() {
  const selection=$('#selection'); selection.replaceChildren(); $('#combined-count-note').hidden=state.subject!=='combined';
  for (const id of state.selected) {
    const s=schoolById(id), chip=document.createElement('span');chip.className='chip';
    chip.innerHTML=`${escapeHTML(displayName(s))}<button aria-label="Remove ${escapeHTML(s.name)}">×</button>`;
    chip.querySelector('button').addEventListener('click',()=>choose(id,false));selection.append(chip);
  }
  let rows=(state.scope==='selected'?cohort().filter(s=>state.selected.has(s.id)):filtered()).filter(s=>metric(s));
  $('.chart-footnote span').textContent = rows.some(s=>!hasInterval(metric(s))) ? 'Sampling intervals unavailable where tested counts are missing' : 'Approximate 95% sampling interval';
  rows.sort((a,b)=>metric(b).studentized-metric(a).studentized);
  const host=$('#residuals'), axisHost=$('#residual-axis');host.replaceChildren();axisHost.replaceChildren();
  if(!rows.length){host.innerHTML='<p class="empty">Select schools from the list or map to compare their residuals.</p>';return;}
  const width=host.clientWidth, left=width<500?132:198, right=44, rowHeight=49;
  const extent=Math.max(2.5,...rows.flatMap(s=>[Math.abs(metric(s).studentized),Math.abs(metric(s).low || 0),Math.abs(metric(s).high || 0)]))+.25;
  const x=d3.scaleLinear().domain([-extent,extent]).range([left,width-right]);
  const axis=d3.select(axisHost).append('svg').attr('viewBox',`0 0 ${width} 27`);
  axis.append('g').attr('class','axis').attr('transform','translate(0,22)').call(d3.axisTop(x).ticks(width<500?3:5).tickSize(0).tickFormat(d=>d===0?'0':signed(d,1))).call(g=>g.select('.domain').remove());
  const svg=d3.select(host).append('svg').attr('viewBox',`0 0 ${width} ${rows.length*rowHeight}`).attr('height',rows.length*rowHeight).attr('role','group').attr('aria-label','Schools sorted by externally studentized residual. Intervals are approximate conditional sampling intervals.');
  const groups=svg.selectAll('g.residual-row').data(rows).join('g').attr('class','residual-row').attr('transform',(s,i)=>`translate(0,${i*rowHeight})`).attr('tabindex',0).attr('role','button').attr('aria-label',s=>`${s.name}, residual ${signed(metric(s).studentized)}, ${intervalLabel(metric(s))}. Inspect school.`).on('click',(e,s)=>inspect(s.id)).on('keydown',(e,s)=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect(s.id);}}).on('mouseenter',tooltip).on('mouseleave',hideTooltip).on('focus',tooltip).on('blur',hideTooltip);
  groups.append('rect').attr('class','row-bg').attr('width',width).attr('height',rowHeight).attr('fill',(s,i)=>s.id===state.focus?'#f3f6ff':i%2?'#fafbfd':'white').attr('rx',3);
  groups.append('line').attr('x1',x(0)).attr('x2',x(0)).attr('y1',0).attr('y2',rowHeight).attr('stroke','#bbc6d5').attr('stroke-dasharray','3 3');
  groups.append('text').attr('x',9).attr('y',21).attr('font-size',12).attr('font-weight',600).attr('fill',color.ink).text(s=>{const n=displayName(s);return n.length>(width<500?18:27)?n.slice(0,width<500?16:25)+'…':n;});
  groups.append('text').attr('x',9).attr('y',37).attr('font-size',12).attr('fill','#667386').text(s=>`${metric(s).tested == null ? 'Count unavailable' : testedLabel(metric(s).tested)}${state.subject==='combined' && metric(s).tested != null?'*':''} · ${pct(s.income)} low income`);
  groups.filter(s=>hasInterval(metric(s))).append('line').attr('x1',s=>x(metric(s).low)).attr('x2',s=>x(metric(s).high)).attr('y1',24).attr('y2',24).attr('stroke',s=>metric(s).studentized>=0?color.above:color.below).attr('stroke-width',2).attr('opacity',.6);
  for(const end of ['low','high'])groups.filter(s=>hasInterval(metric(s))).append('line').attr('x1',s=>x(metric(s)[end])).attr('x2',s=>x(metric(s)[end])).attr('y1',20).attr('y2',28).attr('stroke',s=>metric(s).studentized>=0?color.above:color.below).attr('opacity',.6);
  groups.append('circle').attr('cx',s=>x(metric(s).studentized)).attr('cy',24).attr('r',4.5).attr('fill',s=>metric(s).studentized>=0?color.above:color.below);
  groups.append('text').attr('x',width-4).attr('y',28).attr('text-anchor','end').attr('font-size',12).attr('font-weight',650).attr('fill',s=>metric(s).studentized>=0?color.above:color.below).text(s=>signed(metric(s).studentized));
}
function render(){hideTooltip();const activeId=document.activeElement?.id;renderList();renderMap();renderScatter();renderComparison();renderHistory();syncURL();if(activeId)document.getElementById(activeId)?.focus({preventScroll:true});}
function setFilter(){clearTimeout(searchTimer);listLimit=LIST_PAGE_SIZE;state.query=$('#search').value.trim().toLowerCase();state.program=$('#program').value;ensureFocus();render();announce(`${filtered().length} matching schools. Regression unchanged.`);}
function scheduleSearch(){clearTimeout(searchTimer);searchTimer=setTimeout(setFilter,150);}
async function init(){
  try{
    const catalogResponse = await fetch('data/manifest.json');
    if (!catalogResponse.ok) throw new Error('Dataset catalog unavailable');
    const catalog = await catalogResponse.json();
    const stateSelect = $('#state-select'), regionSelect = $('#region-select');
    stateSelect.replaceChildren(...catalog.states.map(s => new Option(s.name, s.id)));
    const locationState = catalog.states.find(s => s.id === 'IL');
    stateSelect.value = locationState.id;
    regionSelect.replaceChildren(...locationState.regions.map(region => {
      const option = new Option(region.status === 'ready' ? region.name : `${region.name} — in preparation`, region.id);
      option.disabled = region.status !== 'ready';
      return option;
    }));
    const initialParams = new URLSearchParams(window.location.search);
    function selectURLRegion(params) {
      regionSelect.value = locationState.regions.some(r=>r.id===params.get('region') && r.status==='ready') ? params.get('region') : 'chicago';
    }
    selectURLRegion(initialParams);
    let loadVersion = 0;
    async function loadRegion(params = null) {
      const version = ++loadVersion;
      clearTimeout(searchTimer);
      listLimit = LIST_PAGE_SIZE;
      const selectedRegion = locationState.regions.find(r => r.id === regionSelect.value);
      regionSelect.disabled = true;
      try {
        const loaded = await Promise.all([selectedRegion.schools,selectedRegion.boundaries].map(async url=>{if (!url) return null;const r=await fetch(url);if(!r.ok)throw new Error(`${url}: ${r.status}`);return r.json();}));
        if (version !== loadVersion) return;
        [data,geography] = loaded;
        const statewide = selectedRegion.id === 'statewide';
        state.level = 'ES'; $('#level').value = 'ES';
        $('#level option[value="HS"]').disabled = false;
        $('#program').disabled = statewide;
        state.query = ''; state.program = 'all'; $('#search').value = ''; $('#program').value = 'all';
        state.scope = 'selected'; $('#scope').value = state.scope;
        mapSvg = null;
        $('.map-panel h2').textContent = statewide ? 'Across Illinois' : 'Across Chicago';
        $('.intro .eyebrow').textContent = statewide ? 'ILLINOIS PUBLIC SCHOOLS / 2023–24' : 'CHICAGO PUBLIC SCHOOLS / 2023–24';
        $('#map').setAttribute('aria-label', statewide ? 'Illinois school map' : 'Chicago school map');
        $('.map-source').textContent = statewide ? `Locations: NCES 2023–24 · Boundary: Illinois State Geological Survey · ${data.schools.filter(s=>s.latitude!=null&&s.longitude!=null).length} of ${data.schools.length} schools mapped · Scroll or pinch to zoom` : 'Community boundaries: City of Chicago · Scroll or pinch to zoom';
        $('#map-reset').disabled = false;
        $('#geography-note').textContent = statewide ? 'Comparison population: Illinois statewide · 2024 IAR and SAT. Sampling intervals are unavailable where tested counts are missing.' : 'Comparison population: Chicago Public Schools · CPS annual assessment cohorts.';
        $('#coverage').textContent = data.coverage_note || `The directory contains ${data.schools.length} grade and high schools. Math models include ${data.models.ES.math.n} grade schools and ${data.models.HS.math.n} high schools. Data retrieved September 17, 2026.`;
        if (params) restoreURL(params, statewide); else defaults();
        render();
        $('#load-error').hidden = true;
        announce(`${selectedRegion.name} comparisons loaded.`);
      } catch (error) {
        console.error(error); $('#load-error').hidden = false;
      } finally { if (version === loadVersion) regionSelect.disabled = false; }
    }
    regionSelect.addEventListener('change', () => loadRegion());
    window.addEventListener('popstate', () => {
      const params = new URLSearchParams(window.location.search);
      selectURLRegion(params);
      loadRegion(params);
    });
    await loadRegion(initialParams);
    // Keep typing off the synchronous chart-render path; apply the latest query
    // after a short pause. Searching still covers every school, not just this page.
    $('#search').addEventListener('input',scheduleSearch);
    $('#search').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();setFilter();}});
    $('#program').addEventListener('change',setFilter);
    $('#level').addEventListener('change',e=>{clearTimeout(searchTimer);state.query=$('#search').value.trim().toLowerCase();listLimit=LIST_PAGE_SIZE;state.level=e.target.value;defaults();ensureFocus();render();announce('School level changed. Selections reset to this assessment cohort.');});
    document.querySelectorAll('[data-subject]').forEach(button=>button.addEventListener('click',()=>{state.subject=button.dataset.subject;document.querySelectorAll('[data-subject]').forEach(b=>b.setAttribute('aria-pressed',b===button));ensureFocus();render();announce(`${button.textContent} comparison selected.`);}));
    $('#scope').addEventListener('change',e=>{state.scope=e.target.value;renderComparison();syncURL();});
    $('#map-reset').addEventListener('click',()=>mapSvg?.call(mapZoom.transform,d3.zoomIdentity));
    $('#reset').addEventListener('click',()=>{clearTimeout(searchTimer);listLimit=LIST_PAGE_SIZE;state.program='all';state.query='';$('#search').value='';$('#program').value='all';ensureFocus();render();announce('Name and school-type filters reset.');});
    let timer;window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(()=>{renderMap();renderScatter();renderComparison();renderHistory();},150);});
    document.querySelectorAll('a[href="#uncertainty"]').forEach(a=>a.addEventListener('click',()=>{$('#uncertainty').open=true;}));
  }catch(error){console.error(error);$('#load-error').hidden=false;$('#school-count').textContent='Data unavailable';}
}
function initDefinitions() {
  let active = null, timer;
  function close() {
    clearTimeout(timer);
    if (!active) return;
    active.querySelector('.term-definition').hidden = true;
    active.querySelector('button').setAttribute('aria-expanded', 'false');
    active = null;
  }
  function position() {
    if (!active) return;
    const button = active.querySelector('button'), tip = active.querySelector('.term-definition');
    const box = button.getBoundingClientRect();
    tip.style.left = `${Math.max(8, Math.min(box.left, window.innerWidth - tip.offsetWidth - 8))}px`;
    const below = box.bottom + 8;
    tip.style.top = `${Math.max(8, below + tip.offsetHeight <= window.innerHeight - 8 ? below : box.top - tip.offsetHeight - 8)}px`;
  }
  document.querySelectorAll('.term-help').forEach(wrapper => {
    const button = wrapper.querySelector('button');
    function show() {
      if (active !== wrapper) close();
      clearTimeout(timer); active = wrapper;
      wrapper.querySelector('.term-definition').hidden = false;
      button.setAttribute('aria-expanded', 'true'); position();
    }
    wrapper.addEventListener('mouseenter', show);
    wrapper.addEventListener('mouseleave', () => {
      if (document.activeElement !== button) timer = setTimeout(close, 160);
    });
    button.addEventListener('focus', show);
    button.addEventListener('click', show);
    button.addEventListener('blur', close);
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
  document.addEventListener('pointerdown', event => { if (active && !active.contains(event.target)) close(); });
  document.querySelectorAll('.method-details details').forEach(detail => detail.addEventListener('toggle', close));
  window.addEventListener('resize', position);
  window.addEventListener('scroll', position, true);
}
initDefinitions();
init();
