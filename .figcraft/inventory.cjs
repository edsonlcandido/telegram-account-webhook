/* Inventario de gradientes + sombras coloridas em apps/landing e apps/web. */
const fs = require('fs');
const path = require('path');

const roots = ['apps/landing/src', 'apps/web/src'];
const files = [];
const walk = (d) => {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(vue|ts|tsx|css|html)$/.test(e.name)) files.push(p);
  }
};
roots.forEach(walk);

const COLOR = '(?:[a-z]+)-(?:[0-9]{2,3})(?:/[0-9]{1,3})?';
const gradRe = new RegExp(
  'bg-gradient-to-[a-z]+' +
  '(?:\\s+(?:hover|focus|active|disabled|group-hover|sm|md|lg|dark):' + COLOR + ')*' +
  '(?:\\s+(?:hover|focus|active|disabled|group-hover|sm|md|lg|dark):(?:from|via|to)-' + COLOR + ')*' +
  '(?:\\s+(?:from|via|to)-' + COLOR + ')*',
  'g'
);
const shadowRe = new RegExp('shadow-[a-z]+-[0-9]{3}/[0-9]{1,3}', 'g');

const grad = new Map();
const colorShadow = new Map();
let total = 0;

for (const f of files) {
  const src = fs.readFileSync(f, 'utf8');
  for (const m of src.match(gradRe) || []) {
    const key = m.replace(/\s+/g, ' ').trim();
    grad.set(key, (grad.get(key) || 0) + 1);
    total++;
  }
  for (const m of src.match(shadowRe) || []) colorShadow.set(m, (colorShadow.get(m) || 0) + 1);
}

console.log(`=== GRADIENTS (${grad.size} distintos, ${total} ocorrencias) ===`);
[...grad.entries()].sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`${String(v).padStart(3)}x  ${k}`));
console.log('\n=== SOMBRAS COLORIDAS ===');
[...colorShadow.entries()].sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`${String(v).padStart(3)}x  ${k}`));