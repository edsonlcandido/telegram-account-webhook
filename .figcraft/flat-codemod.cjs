/* ============================================================================
   Codemod: landing + web app -> paleta flat (Telegram blue primary).
   - gradientes colapsam em cor solida (first `from-` define a familia)
   - texto-gradiente vira texto solido
   - familia blue/cyan/sky/indigo -> brand (#229ED9)
   - familia purple/violet/fuchsia/pink/magenta -> accent (#7C5CFC)
   - verde/amarelo/vermelho/cinza intactos (semanticos)
   - sombras coloridas (glow de gradiente) removidas
   ========================================================================== */
const fs = require('fs');
const path = require('path');

const BRAND = new Set(['blue', 'sky', 'cyan', 'indigo']);
const ACCENT = new Set(['purple', 'violet', 'fuchsia', 'pink', 'magenta']);
const RED = new Set(['red', 'rose']);

/* overrides 1:1 com o mockup flat aprovado no FigCraft (cada padrao e unico no app) */
const RAW_OVERRIDES = [
  ['bg-gradient-to-br from-purple-600 via-pink-500 to-orange-400', 'bg-brand-500'], // CTA landing
  ['bg-gradient-to-br from-green-500 to-green-600', 'bg-accent-500'],              // card Webhooks Config
  ['bg-gradient-to-r from-green-50 to-green-100', 'bg-accent-50'],                // faixa do card Webhooks
  ['bg-gradient-to-br from-purple-500 to-purple-600', 'bg-green-500'],             // card Status = success
  ['text-xs text-green-700 font-medium', 'text-xs text-accent-700 font-medium'],  // texto da faixa Webhooks
];

const family = (c) => (BRAND.has(c) ? 'brand' : ACCENT.has(c) ? 'accent' : RED.has(c) ? 'red' : c);

function remapColorToken(token) {
  // [variantes:] [utilitario-] cor-shade(/alpha)  ex: focus:ring-blue-500, border-purple-300
  const m = token.match(/^((?:[a-z]+-)*[a-z]+:)?((?:[a-z]+-)*)([a-z]+)-([0-9]{2,3})(\/[0-9]{1,3})?$/);
  if (!m) return token;
  const [, variant, util, color, shade, alpha = ''] = m;
  const fam = family(color);
  if (fam === color) return token;
  return `${variant || ''}${util}${fam}-${shade}${alpha}`;
}

const isGlowShadow = (t) => /^(?:[a-z-]+:)?shadow-[a-z]+-[0-9]{3}\/[0-9]{1,3}$/.test(t);
const isClipText = (t) => t === 'bg-clip-text' || t === 'text-transparent';
const isGradientFrom = (t) => /^(?:[a-z-]+:)?from-[a-z]+-[0-9]{2,3}(?:\/[0-9]{1,3})?$/.test(t);
const isGradientStop = (t) => /^(?:[a-z-]+:)?(?:from|via|to)-[a-z]+-[0-9]{2,3}(?:\/[0-9]{1,3})?$/.test(t);

function processClassString(cls) {
  const tokens = cls.split(/\s+/).filter(Boolean);
  const asText = tokens.includes('bg-clip-text');
  const out = [];
  let i = 0;
  while (i < tokens.length) {
    const t = tokens[i];
    if (/^bg-gradient-to-[a-z]+$/.test(t)) {
      i++;
      while (i < tokens.length && isGradientStop(tokens[i])) {
        const tk = tokens[i];
        if (isGradientFrom(tk)) {
          const m = tk.match(/^((?:[a-z-]+:)?)from-([a-z]+)-([0-9]{2,3})(\/[0-9]{1,3})?$/);
          if (m) out.push(`${m[1]}${asText ? 'text' : 'bg'}-${family(m[2])}-${m[3]}${m[4] || ''}`);
        }
        i++;
      }
      continue;
    }
    if (isGlowShadow(t)) { i++; continue; }
    if (asText && isClipText(t)) { i++; continue; }
    // stops soltos: variantes de hover/focus que ficam depois de outras utilities
    const stop = t.match(/^((?:[a-z-]+:)?)(from|via|to)-([a-z]+)(?:-([0-9]{2,3}))?((?:\/[0-9]{1,3})?)$/);
    if (stop) {
      if (stop[2] === 'from') out.push(`${stop[1]}${asText ? 'text' : 'bg'}-${family(stop[3])}${stop[4] ? `-${stop[4]}` : ''}${stop[5] || ''}`);
      i++;
      continue;
    }
    out.push(remapColorToken(t));
    i++;
  }
  return out.join(' ');
}

/* :class="cond ? 'a b' : 'c d'" — processa cada literal, nunca o operador ternario */
const HUE_TOKEN = /(?:^|\s)(?:[a-z-]+:)*(?:[a-z]+-)*(blue|purple|pink|cyan|indigo|sky|rose|fuchsia|violet|magenta)-\d{2,3}/;
function processClassValue(value) {
  if (!value.includes("'")) return processClassString(value);
  return value.replace(/'([^']*)'/g, (m, inner) => {
    const hasStop = /\b(from|via|to)-[a-z]+-\d/.test(inner);
    return hasStop || HUE_TOKEN.test(inner) ? `'${processClassString(inner)}'` : m;
  });
}

function processFile(file, report) {
  let src = fs.readFileSync(file, 'utf8');
  const before = src;
  for (const [from, to] of RAW_OVERRIDES) src = src.split(from).join(to);

  let inClass = 0;
  src = src.replace(/(?<![-\w])class="([^"]*)"/g, (_m, inner) => {
    inClass++;
    return `class="${processClassValue(inner)}"`;
  });

  if (src !== before) {
    fs.writeFileSync(file, src, 'utf8');
    report.push({ file, attrs: inClass });
    return true;
  }
  return false;
}

const files = [];
const walk = (d) => {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(vue|ts|tsx)$/.test(e.name)) files.push(p);
  }
};
['apps/landing/src', 'apps/web/src'].forEach(walk);

const report = [];
for (const f of files) processFile(f, report);

for (const r of report) console.log(`${r.file}  (${r.attrs} atributos class reescritos)`);
console.log(`\n${report.length} arquivos alterados de ${files.length}.`);