const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function app() {
  const controls = Object.fromEntries(['state-select','region-select','program','level','search','scope'].map(id=>['#'+id,{value:''}]));
  controls['#state-select'].value = 'IL';
  controls['#region-select'].value = 'statewide';
  controls['#program'].options = ['all','Neighborhood','Selective'].map(value=>({value}));
  const window = {location:{href:'https://example.org/FRPL-RMA/?other=kept#workspace'},history:{replaceState(_a,_b,url){window.location.href=url.href;}}};
  const context = vm.createContext({URL,URLSearchParams,window,document:{querySelector:s=>controls[s],querySelectorAll:()=>[]}});
  vm.runInContext(fs.readFileSync('app.js','utf8').replace(/initDefinitions\(\);\s*init\(\);\s*$/, ''), context);
  vm.runInContext(`data={schools:[
    {id:'001',level:'ES',name:'Alpha',short:'Alpha',program:'Neighborhood',metrics:{combined:{},math:{},reading:{}}},
    {id:'002',level:'ES',name:'Beta',short:'Beta',program:'Selective',metrics:{combined:{},math:{},reading:{}}},
    {id:'003',level:'HS',name:'Gamma',short:'Gamma',program:'Neighborhood',metrics:{combined:{},math:{},reading:{}}}
  ]};`,context);
  return {run:code=>vm.runInContext(code,context),window};
}

test('restores share links without forcing focus or selections into search results',()=>{
  const a=app();
  a.run(`restoreURL(new URLSearchParams('level=ES&subject=ela&q=alpha&schools=002,001&focus=002&scope=filtered'),true);syncURL();`);
  const p=new URL(a.window.location.href).searchParams;
  assert.equal(p.get('schools'),'002,001');
  assert.equal(p.get('focus'),'002');
  assert.equal(p.get('subject'),'ela');
  assert.equal(p.get('q'),'alpha');
  assert.equal(p.get('scope'),'filtered');
  assert.equal(p.get('other'),'kept');
  assert.equal(new URL(a.window.location.href).hash,'#workspace');
});
test('explicit empty selection survives reload, while absent selection gets defaults',()=>{
  const a=app();
  a.run(`restoreURL(new URLSearchParams('schools='),true);syncURL();`);
  assert.equal(new URL(a.window.location.href).searchParams.get('schools'),'');
  a.run(`restoreURL(new URLSearchParams(),true);syncURL();`);
  assert.equal(new URL(a.window.location.href).searchParams.get('schools'),'001');
});
test('invalid filters and foreign school IDs are safely normalized',()=>{
  const a=app();
  a.run(`restoreURL(new URLSearchParams('level=bad&subject=bad&program=bad&schools=003,unknown,001,001&focus=unknown'),true);syncURL();`);
  const p=new URL(a.window.location.href).searchParams;
  assert.equal(p.get('schools'),'001');
  assert.equal(p.get('level'),'ES');
  assert.equal(p.get('subject'),'combined');
  assert.equal(p.get('program'),'all');
  assert.equal(p.get('focus'),'001');
});
test('query punctuation and high-school state round-trip',()=>{
  const a=app();
  a.run(`restoreURL(new URLSearchParams({q:'A & B + C',level:'HS',subject:'math',schools:'003',focus:'003'}),false);syncURL();`);
  const first=a.window.location.href;
  a.run(`restoreURL(new URL(window.location.href).searchParams,false);syncURL();`);
  assert.equal(a.window.location.href,first);
  assert.equal(new URL(first).searchParams.get('q'),'a & b + c');
});
test('verified CPS program filters survive statewide share links',()=>{
  const a=app();
  a.run(`restoreURL(new URLSearchParams('program=Selective&schools=002&focus=002'),true);syncURL();`);
  const first=a.window.location.href;
  assert.equal(new URL(first).searchParams.get('program'),'Selective');
  a.run(`restoreURL(new URL(window.location.href).searchParams,true);syncURL();`);
  assert.equal(a.window.location.href,first);
});
test('state and region resolve together, with safe cross-state fallbacks',()=>{
  const a=app();
  a.run(`catalogForTest={states:[{id:'IL',regions:[{id:'chicago',status:'ready'},{id:'statewide',status:'ready'}]},{id:'NY',regions:[{id:'nyc',status:'ready'}]}]};`);
  assert.equal(a.run(`resolveGeography(catalogForTest,new URLSearchParams('state=NY&region=nyc')).region.id`),'nyc');
  assert.equal(a.run(`resolveGeography(catalogForTest,new URLSearchParams('state=NY&region=chicago')).region.id`),'nyc');
  assert.equal(a.run(`resolveGeography(catalogForTest,new URLSearchParams('state=unknown&region=nyc')).region.id`),'chicago');
  assert.equal(a.run(`resolveGeography(catalogForTest,new URLSearchParams('region=statewide')).region.id`),'statewide');
});
test('NYC share links retain DBNs and reject unavailable admissions filters',()=>{
  const a=app();
  a.run(`document.querySelector('#state-select').value='NY'; document.querySelector('#region-select').value='nyc';
    document.querySelector('#program').options.find(o=>o.value==='Selective').disabled=true;
    data.schools[0].id='01M015';data.schools[1].id='01M020';data.schools[2].id='02M475';
    restoreURL(new URLSearchParams('level=HS&schools=02M475&focus=02M475&program=Selective&q=stuyvesant'),false);syncURL();`);
  const p=new URL(a.window.location.href).searchParams;
  assert.equal(p.get('state'),'NY');assert.equal(p.get('region'),'nyc');
  assert.equal(p.get('schools'),'02M475');assert.equal(p.get('focus'),'02M475');
  assert.equal(p.get('program'),'all');
});

test('Wisconsin share links resolve and round-trip DPI school IDs',()=>{
  const a=app();
  a.run(`catalogForTest={states:[{id:'IL',regions:[{id:'chicago',status:'ready'}]},{id:'WI',regions:[{id:'wisconsin',status:'ready'}]}]};`);
  assert.equal(a.run(`resolveGeography(catalogForTest,new URLSearchParams('state=WI&region=wisconsin')).region.id`),'wisconsin');
  assert.equal(a.run(`resolveGeography(catalogForTest,new URLSearchParams('state=WI&region=nyc')).region.id`),'wisconsin');
  assert.equal(a.run(`resolveGeography(catalogForTest,new URLSearchParams('state=unknown&region=wisconsin')).region.id`),'chicago');
  a.run(`document.querySelector('#state-select').value='WI'; document.querySelector('#region-select').value='wisconsin';
    data.schools[0].id='S00070020';data.schools[1].id='S00070040';data.schools[2].id='S25760040';
    restoreURL(new URLSearchParams('level=ES&subject=ela&schools=S00070040&focus=S00070040&q=abbotsford'),false);syncURL();`);
  const p=new URL(a.window.location.href).searchParams;
  assert.equal(p.get('state'),'WI');assert.equal(p.get('region'),'wisconsin');
  assert.equal(p.get('schools'),'S00070040');assert.equal(p.get('focus'),'S00070040');
  assert.equal(p.get('subject'),'ela');assert.equal(p.get('q'),'abbotsford');
});

test('NYC multi-program filters match either label and survive a shared URL',()=>{
  const a=app();
  a.run(`document.querySelector('#program').options=['all','Zoned','Gifted & Talented','Unclassified'].map(value=>({value}));
    data.schools[0].programs=['Zoned','Gifted & Talented'];
    data.schools[1].programs=['Unclassified'];
    restoreURL(new URLSearchParams({program:'Gifted & Talented',schools:'001'}),false);syncURL();`);
  assert.equal(a.run(`filtered().map(s=>s.id).join(',')`),'001');
  assert.equal(new URL(a.window.location.href).searchParams.get('program'),'Gifted & Talented');
  a.run(`restoreURL(new URL(window.location.href).searchParams,false);syncURL();`);
  assert.equal(a.run(`filtered().length`),1);
  a.run(`state.program='Zoned'`);
  assert.equal(a.run(`filtered()[0].id`),'001');
  a.run(`state.program='Unclassified'`);
  assert.equal(a.run(`filtered()[0].id`),'002');
  assert.equal(a.run(`matchesProgram({program:'Neighborhood'},'Neighborhood')`),true);
});
