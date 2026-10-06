const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {textContent:'', disabled:false, checked:false,
    addEventListener(event, callback) {this[event] = callback;}});
  return nodes.get(id);
}
const state = {installed_version:'0.1.11', latest_version:'0.1.12', source_channel:'develop', installed_channel:'develop', update_available:true, worker:{}};
let fail = true;
const context = vm.createContext({document:{getElementById:node}, window:{confirm:()=>true},
  fetch: async () => ({ok:!fail, statusText:'Failed', json:async()=>fail?{error:'sudo: The no new privileges flag is set'}:state}),
  setTimeout, console});
let source=fs.readFileSync(path.join(__dirname,'../ais_atis_bridge/static/app.js'),'utf8');
source=source.replace(/\nrefresh\(\);\nsetInterval\(refresh, 2000\);\s*$/, '\n');
vm.runInContext(source, context);
const render=()=>vm.runInContext('renderUpdate('+JSON.stringify(state)+')',context);
(async()=>{
  render();
  await node('install-update').click();
  assert.match(node('update-message').textContent, /no new privileges/);
  render();render();
  assert.match(node('update-message').textContent, /no new privileges/, 'status polling erased install failure');
  assert.equal(node('install-update').disabled, false, 'retry remains available');
  fail=false;
  await node('check-update').click();
  assert.match(node('update-message').textContent, /0.1.12 is ready/, 'explicit check clears error');
  fail=true;
  await node('beta-toggle').change();
  render();
  assert.match(node('update-message').textContent, /no new privileges/, 'channel failure should persist');
  console.log('PASS updater errors persist across polls; explicit check clears errors; retry controls recover');
})().catch(e=>{console.error(e);process.exitCode=1;});
