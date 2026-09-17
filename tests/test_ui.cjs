const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const html = fs.readFileSync(path.join(__dirname, '../ais_atis_bridge/templates/index.html'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../ais_atis_bridge/static/style.css'), 'utf8');
for (const id of ['state','identity','show-map','auto-map','map-zoom','audio-toggle','receiver','tuning_mode','selected_channel','gain_mode','gain_db','squelch_mode','squelch_threshold_dbfs','scan_speed','scan_speed_value','channels','stop','xlsx','message']) {
  assert(html.includes(`id="${id}"`), `missing UI id ${id}`);
}
assert(html.includes('min="100" max="500" step="50" value="200"'));
assert(html.includes('min="3" max="18" step="1" value="14"'));
assert(css.includes('--cyan:#38bdf8'));
assert(css.includes('.success{'));
assert(css.includes('.danger{'));
console.log('PASS UI contract: SDRCC-style controls, zoom and scan-speed widgets present');
