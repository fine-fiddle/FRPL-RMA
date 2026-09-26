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
