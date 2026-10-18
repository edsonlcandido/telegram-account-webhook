/* Le o document.json de dentro do .figcraft (zip) e extrai a paleta da frame flat. */
const fs = require('fs');
const zlib = require('zlib');

function readZipEntry(buf, name) {
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0 && i > buf.length - 200000; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  const count = buf.readUInt16LE(eocd + 10);
  let off = buf.readUInt32LE(eocd + 16);
  for (let n = 0; n < count; n++) {
    const method = buf.readUInt16LE(off + 10);
    const csize = buf.readUInt32LE(off + 20);
    const nameLen = buf.readUInt16LE(off + 28);
    const extraLen = buf.readUInt16LE(off + 30);
    const commentLen = buf.readUInt16LE(off + 32);
    const lho = buf.readUInt32LE(off + 42);
    const entryName = buf.slice(off + 46, off + 46 + nameLen).toString('utf8');
    if (entryName === name) {
      const l = lho + 30 + buf.readUInt16LE(lho + 26) + buf.readUInt16LE(lho + 28);
      const raw = buf.slice(l, l + csize);
      return method === 0 ? raw : zlib.inflateRawSync(raw);
    }
    off += 46 + nameLen + extraLen + commentLen;
  }
  throw new Error('entrada nao encontrada: ' + name);
}

const doc = JSON.parse(readZipEntry(fs.readFileSync('docs/design/hub.figcraft'), 'document.json').toString('utf8'));
const N = doc.nodes;

const walk = (id, out = []) => {
  const n = N[id];
  if (!n) return out;
  out.push(n);
  for (const c of n.children || []) walk(c, out);
  return out;
};

const hex = (c) => {
  if (typeof c === 'string') return c;
  if (!c) return '?';
  const b = (v) => Math.round(v * 255).toString(16).padStart(2, '0');
  return `#${b(c.r)}${b(c.g)}${b(c.b)}`.toUpperCase();
};

for (const [id, label] of [[1739, 'Landing flat'], [2190, 'Dashboard flat']]) {
  const nodes = walk(id);
  const fills = new Map();
  for (const n of nodes) {
    for (const p of n.fills || []) {
      if (p.type !== 'solid') { fills.set('GRADIENT', (fills.get('GRADIENT') || 0) + 1); continue; }
      const key = hex(p.color) + (p.opacity !== undefined && p.opacity !== 1 ? `@${Math.round(p.opacity * 100)}%` : '');
      fills.set(key, (fills.get(key) || 0) + 1);
    }
  }
  const strokes = new Map();
  for (const n of nodes) for (const p of n.strokes || []) strokes.set(hex(p.color), (strokes.get(hex(p.color)) || 0) + 1);
  console.log(`\n=== ${label} (${nodes.length} layers) ===`);
  console.log('fills  :', [...fills.entries()].sort((a, b) => b[1] - a[1]).map(([c, k]) => `${c}×${k}`).join('  '));
  console.log('strokes:', [...strokes.entries()].sort((a, b) => b[1] - a[1]).map(([c, k]) => `${c}×${k}`).join('  '));
}