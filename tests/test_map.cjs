// Run with node tests/test_map.cjs; no browser or receiver is required.
const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
const nodes = Object.fromEntries(['show-map', 'auto-map', 'map-message'].map(id => [id, {
  disabled: true, textContent: '', addEventListener(event, fn) { this[event] = fn; }, setAttribute() {}
}]));
let opens = 0, blocked = false;
const map = {closed: false, location: {href: ''}, focus() {}};
const window = {location: {hostname: 'receiver.local'}, open(url, name) {
  if (blocked) return null;
  opens++; assert.equal(name, 'ais-atis-bridge-map'); map.location.href = url; return map;
}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../ais_atis_bridge/static/map.js'), 'utf8'), {
  window, URL, document: {getElementById: id => nodes[id]}
});
const state = {settings: {ais_viewer_url: 'http://127.0.0.1:8119/'}, receiver: {latest: null}, ais_match: null};
window.atisMap.update(state); nodes['auto-map'].click();
assert.equal(opens, 1); assert.equal(nodes['auto-map'].textContent, 'Auto: on');
assert(map.location.href.startsWith('http://receiver.local:8119/'));
state.receiver.latest = {fresh: true}; state.ais_match = {matched: true, mmsi: '244123456'};
window.atisMap.update(state); assert(map.location.href.includes('mmsi=244123456'));
state.ais_match.mmsi = '244654321'; window.atisMap.update(state);
assert(map.location.href.includes('mmsi=244654321')); assert.equal(opens, 1);
const last = map.location.href;
state.receiver.latest.fresh = false; state.ais_match.mmsi = '244999999'; window.atisMap.update(state);
assert.equal(map.location.href, last); assert(nodes['show-map'].disabled);
nodes['auto-map'].click(); assert.equal(nodes['auto-map'].textContent, 'Auto: off');
state.receiver.latest.fresh = true; window.atisMap.update(state); assert.equal(map.location.href, last);
nodes['auto-map'].click(); map.closed = true; window.atisMap.update(state);
assert.equal(nodes['auto-map'].textContent, 'Auto: off');
blocked = true; nodes['auto-map'].click(); assert.equal(nodes['auto-map'].textContent, 'Auto: off');
assert(nodes['map-message'].textContent.includes('pop-ups'));
window.atisMap.offline(); assert(nodes['show-map'].disabled);
console.log('PASS map controls: one window, new vessel, stale match, Auto off, closed window, blocked popup, offline');
