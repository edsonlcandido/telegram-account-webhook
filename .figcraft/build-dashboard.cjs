/* Dashboard do Telegram Webhook Hub — 2 frames no mesmo documento:
 *   x=3200  "Dashboard — Atual"        (recriacao fiel do app em producao)
 *   x=4800  "Dashboard — Flat · Azul Telegram" (cores flat, primary #229ED9)
 *
 * Um unico build deterministico de zero (frames novos). Qualquer ajuste
 * posterior deve ser set_properties, nunca re-run deste script.
 */
const M = require('C:/Users/edson/.minimax/agents/mavis/skills/figcraft-ui-prototyper/scripts/mcp-client.js');
const { createNode, setProps, runCommand, saveFile } = M;

const SRC = 'D:/repos/telegram-account-webhook/docs/design/hub.figcraft';
const PAGE_W = 1440;
const CONTENT_W = 1280; // max-w-7xl

/* ---------- paints ---------- */
const S = (hex, opacity) => {
  const p = { type: 'solid', color: hex };
  if (opacity !== undefined) p.opacity = opacity;
  return p;
};
const g = (dir, stops) => {
  const s = stops.map((color, i) => ({ position: stops.length === 1 ? 0 : i / (stops.length - 1), color }));
  if (dir === 'r') return [{ type: 'gradient', from: [0, 0.5], to: [1, 0.5], width: [-1, 0], stops: s }];
  if (dir === 'b') return [{ type: 'gradient', from: [0.5, 0], to: [0.5, 1], width: [-0.5, 0], stops: s }];
  return [{ type: 'gradient', from: [0, 0], to: [1, 1], width: [1, -1], stops: s }];
};
const SHADOW = (a = '0F172A14', radius = 28, y = 10) => [{ type: 'dropShadow', color: a, offset: [0, y], radius, spread: 0 }];

/* ---------- heroicons 24/solid ---------- */
const ICONS = {
  phone: 'M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z',
  link: 'M19.902 4.098a3.75 3.75 0 0 0-5.304 0l-4.5 4.5a3.75 3.75 0 0 0 1.035 6.037.75.75 0 0 1-.646 1.353 5.25 5.25 0 0 1-1.449-8.45l4.5-4.5a5.25 5.25 0 1 1 7.424 7.424l-1.757 1.757a.75.75 0 1 1-1.06-1.06l1.757-1.757a3.75 3.75 0 0 0 0-5.304Zm-7.389 4.267a.75.75 0 0 1 1-.353 5.25 5.25 0 0 1 1.449 8.45l-4.5 4.5a5.25 5.25 0 1 1-7.424-7.424l1.757-1.757a.75.75 0 1 1 1.06 1.06l-1.757 1.757a3.75 3.75 0 1 0 5.304 5.304l4.5-4.5a3.75 3.75 0 0 0-1.035-6.037.75.75 0 0 1-.354-1Z',
  check: 'M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm13.36-1.814a.75.75 0 1 0-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.14-.094l3.75-5.25Z',
  chat: 'M4.913 2.658c2.075-.27 4.19-.408 6.337-.408 2.147 0 4.262.139 6.337.408 1.922.25 3.291 1.861 3.405 3.727a4.403 4.403 0 0 0-1.032-.211 50.89 50.89 0 0 0-8.42 0c-2.358.196-4.04 2.19-4.04 4.434v4.286a4.47 4.47 0 0 0 2.433 3.984L7.28 21.53A.75.75 0 0 1 6 21v-4.03a48.527 48.527 0 0 1-1.087-.128C2.905 16.58 1.5 14.833 1.5 12.862V6.638c0-1.97 1.405-3.718 3.413-3.979ZM15.75 7.5c-1.376 0-2.739.057-4.086.169C10.124 7.797 9 9.103 9 10.609v4.285c0 1.507 1.128 2.814 2.67 2.94 1.243.102 2.5.157 3.768.165l2.782 2.781a.75.75 0 0 0 1.28-.53v-2.39l.33-.026c1.542-.125 2.67-1.433 2.67-2.94v-4.286c0-1.505-1.125-2.811-2.664-2.94A49.392 49.392 0 0 0 15.75 7.5Z',
  send: 'M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z',
  trash: 'M16.5 4.478v.227a48.816 48.816 0 0 1 3.878.512.75.75 0 1 1-.256 1.478l-.209-.035-1.005 13.07a3 3 0 0 1-2.991 2.77H8.084a3 3 0 0 1-2.991-2.77L4.087 6.66l-.209.035a.75.75 0 0 1-.256-1.478A48.567 48.567 0 0 1 7.5 4.705v-.227c0-1.564 1.213-2.9 2.816-2.951a52.662 52.662 0 0 1 3.369 0c1.603.051 2.815 1.387 2.815 2.951Zm-6.136-1.452a51.196 51.196 0 0 1 3.273 0C14.39 3.05 15 3.684 15 4.478v.113a49.488 49.488 0 0 0-6 0v-.113c0-.794.609-1.428 1.364-1.452Zm-.355 5.945a.75.75 0 1 0-1.5.058l.347 9a.75.75 0 1 0 1.499-.058l-.346-9Zm5.48.058a.75.75 0 1 0-1.498-.058l-.347 9a.75.75 0 0 0 1.5.058l.345-9Z',
  doc: 'M5.625 1.5c-1.036 0-1.875.84-1.875 1.875v17.25c0 1.035.84 1.875 1.875 1.875h12.75c1.035 0 1.875-.84 1.875-1.875V12.75A3.75 3.75 0 0 0 16.5 9h-1.875a1.875 1.875 0 0 1-1.875-1.875V5.25A3.75 3.75 0 0 0 9 1.5H5.625ZM7.5 15a.75.75 0 0 1 .75-.75h7.5a.75.75 0 0 1 0 1.5h-7.5A.75.75 0 0 1 7.5 15Zm.75 2.25a.75.75 0 0 0 0 1.5H12a.75.75 0 0 0 0-1.5H8.25ZM12.971 1.816A5.23 5.23 0 0 1 14.25 5.25v1.875c0 .207.168.375.375.375H16.5a5.23 5.23 0 0 1 3.434 1.279 9.768 9.768 0 0 0-6.963-6.963Z',
  pencil: 'M21.731 2.269a2.625 2.625 0 0 0-3.712 0l-1.157 1.157 3.712 3.712 1.157-1.157a2.625 2.625 0 0 0 0-3.712ZM19.513 8.199l-3.712-3.712-8.4 8.4a5.25 5.25 0 0 0-1.32 2.214l-.8 2.685a.75.75 0 0 0 .933.933l2.685-.8a5.25 5.25 0 0 0 2.214-1.32l8.4-8.4ZM5.25 5.25a3 3 0 0 0-3 3v10.5a3 3 0 0 0 3 3h10.5a3 3 0 0 0 3-3V13.5a.75.75 0 0 0-1.5 0v5.25a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5V8.25a1.5 1.5 0 0 1 1.5-1.5h5.25a.75.75 0 0 0 0-1.5H5.25Z',
  logout: 'M7.5 3.75A1.5 1.5 0 0 0 6 5.25v13.5a1.5 1.5 0 0 0 1.5 1.5h6a1.5 1.5 0 0 0 1.5-1.5V15a.75.75 0 0 1 1.5 0v3.75a3 3 0 0 1-3 3h-6a3 3 0 0 1-3-3V5.25a3 3 0 0 1 3-3h6a3 3 0 0 1 3 3V9A.75.75 0 0 1 15 9V5.25a1.5 1.5 0 0 0-1.5-1.5h-6Zm10.72 4.72a.75.75 0 0 1 1.06 0l3 3a.75.75 0 0 1 0 1.06l-3 3a.75.75 0 1 1-1.06-1.06l1.72-1.72H9a.75.75 0 0 1 0-1.5h10.94l-1.72-1.72a.75.75 0 0 1 0-1.06Z',
  user: 'M18.685 19.097A9.723 9.723 0 0 0 21.75 12c0-5.385-4.365-9.75-9.75-9.75S2.25 6.615 2.25 12a9.723 9.723 0 0 0 3.065 7.097A9.716 9.716 0 0 0 12 21.75a9.716 9.716 0 0 0 6.685-2.653Zm-12.54-1.285A7.486 7.486 0 0 1 12 15a7.486 7.486 0 0 1 5.855 2.812A8.224 8.224 0 0 1 12 20.25a8.224 8.224 0 0 1-5.855-2.438ZM15.75 9a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z',
  plus: 'M12 4.5a.75.75 0 01.75.75v6h6a.75.75 0 010 1.5h-6v6a.75.75 0 01-1.5 0v-6h-6a.75.75 0 010-1.5h6v-6A.75.75 0 0112 4.5z',
};

/* ---------- temas ---------- */
const THEMES = {
  atual: {
    name: 'Dashboard — Atual',
    page: g('br', ['#F9FAFB', '#EFF6FF', '#FAF5FF']),
    navFill: [S('#FFFFFF', 0.86)],
    navStroke: '#E5E7EB',
    titlePaint: g('r', ['#2563EB', '#9333EA']),
    muted: '#6B7280',
    strong: '#111827',
    heroPaint: g('br', ['#3B82F6', '#A855F7', '#EC4899']),
    heroSub: '#DBEAFE',
    cardFill: [S('#FFFFFF')],
    cardStroke: null,
    cardEffect: SHADOW('0F172A1F'),
    icons: [g('br', ['#3B82F6', '#2563EB']), g('br', ['#22C55E', '#16A34A']), g('br', ['#A855F7', '#7C3AED'])],
    strips: [g('r', ['#EFF6FF', '#DBEAFE']), g('r', ['#F0FDF4', '#DCFCE7']), g('r', ['#FAF5FF', '#F3E8FF'])],
    stripText: ['#1D4ED8', '#15803D', '#7E22CE'],
    cta: g('r', ['#3B82F6', '#A855F7']),
    avatar: g('br', ['#3B82F6', '#9333EA']),
    userPill: g('r', ['#EFF6FF', '#FAF5FF']),
    logoutFill: g('r', ['#EF4444', '#EC4899']),
    actions: [
      { stroke: '#93C5FD', icon: '#2563EB', text: '#2563EB' },
      { stroke: '#D8B4FE', icon: '#9333EA', text: '#9333EA' },
      { stroke: '#86EFAC', icon: '#16A34A', text: '#16A34A' },
      { stroke: '#FCA5A5', icon: '#DC2626', text: '#DC2626' },
    ],
    cardStrokeOn: false,
  },
  flat: {
    name: 'Dashboard — Flat · Azul Telegram',
    page: [S('#F2F6FA')],
    navFill: [S('#FFFFFF')],
    navStroke: '#E3E8EF',
    titlePaint: [S('#0F172A')],
    muted: '#64748B',
    strong: '#0F172A',
    heroPaint: [S('#229ED9')],
    heroSub: '#D6EEF9',
    cardFill: [S('#FFFFFF')],
    cardStroke: '#E3E8EF',
    cardEffect: [],
    // primary #229ED9 (Contas), secundaria #7C5CFC (Webhooks), success (Status)
    icons: [[S('#229ED9')], [S('#7C5CFC')], [S('#16A34A')]],
    strips: [[S('#EAF4FA')], [S('#F1EFFE')], [S('#E8F7EE')]],
    stripText: ['#1B7FB0', '#5B3FD6', '#15803D'],
    cta: [S('#229ED9')],
    avatar: [S('#229ED9')],
    userPill: [S('#EAF4FA')],
    logoutFill: [S('#E5484D')],
    actions: [
      { stroke: '#229ED9', icon: '#229ED9', text: '#1B7FB0' },
      { stroke: '#CBD5E1', icon: '#475569', text: '#475569' },
      { stroke: '#CBD5E1', icon: '#475569', text: '#475569' },
      { stroke: '#F2B8B5', icon: '#E5484D', text: '#E5484D' },
    ],
    cardStrokeOn: true,
  },
};

/* ---------- helpers ---------- */
let iconQueue = [];
const icon = async (parent, name, key, size, color) => {
  const r = await createNode({ type: 'vector', name, parent, path: ICONS[key], props: { fills: [S(color)], sizingH: 'fixed', sizingV: 'fixed' } });
  iconQueue.push({ id: r.id, size });
  return r.id;
};
const flushIcons = async () => {
  const bySize = new Map();
  for (const it of iconQueue) {
    if (!bySize.has(it.size)) bySize.set(it.size, []);
    bySize.get(it.size).push(it.id);
  }
  for (const [size, ids] of bySize) await setProps({ ids, props: { width: size, height: size } });
  iconQueue = [];
};

const frame = async (parent, name, props, opts = {}) => {
  const p = { ...props };
  if (p.layout && p.sizingH === undefined && opts.width === undefined) p.sizingH = 'hug';
  if (p.layout && p.sizingV === undefined && opts.height === undefined) p.sizingV = 'hug';
  if (p.fills === undefined) p.fills = [];
  const params = { type: 'frame', name, parent, props: p };
  if (opts.width !== undefined) params.width = opts.width;
  if (opts.height !== undefined) params.height = opts.height;
  return (await createNode(params)).id;
};

const txt = async (parent, name, chars, o) => {
  const r = await createNode({
    type: 'text', name, parent, text: chars,
    props: {
      fills: typeof o.color === 'string' ? [S(o.color)] : o.color,
      fontFamily: 'Inter', fontStyle: o.weight || 'Regular', fontSize: o.size,
      letterSpacing: o.spacing || '0%', lineHeight: o.lineHeight || '120%',
      ...(o.align ? { textAlign: o.align } : {}),
    },
  });
  return r.id;
};

const pill = (t, parent, name, label, dotColor, bg, fg) =>
  frame(parent, name, {
    layout: 'horizontal', gap: 6, padding: [4, 8], cornerRadius: 999,
    crossAlign: 'center', fills: [S(bg)],
  }).then(async (id) => {
    if (dotColor) await createNode({ type: 'ellipse', name: 'dot', parent: id, width: 6, height: 6, props: { fills: [S(dotColor)], sizingH: 'fixed', sizingV: 'fixed' } });
    await txt(id, 'label', label, { size: 12, weight: 'Medium', color: fg });
    return id;
  });

/* ---------- build ---------- */
async function buildDashboard(x, T) {
  const root = (await createNode({
    type: 'frame', name: T.name, x, y: 0, width: PAGE_W,
    props: { fills: T.page, layout: 'vertical', gap: 0, crossAlign: 'center', sizingH: 'fixed', sizingV: 'hug', clip: true },
  })).id;

  /* 01 Nav ------------------------------------------------------------- */
  const nav = await frame(root, '01 Nav', {
    layout: 'horizontal', mainAlign: 'center', crossAlign: 'center', gap: 0,
    fills: T.navFill, strokes: [S(T.navStroke)], strokeWeight: 1, strokeAlign: 'inside', strokeBottomWeight: 1,
    sizingH: 'fill',
  }, { width: PAGE_W, height: 64 });

  const navIn = await frame(nav, 'nav inner', {
    layout: 'horizontal', mainAlign: 'spaceBetween', crossAlign: 'center', gap: 16,
  }, { width: CONTENT_W, height: 64 });

  await txt(navIn, 'nav title', 'Dashboard', { size: 24, weight: 'Bold', color: T.titlePaint });

  const navRight = await frame(navIn, 'nav actions', { layout: 'horizontal', gap: 12, crossAlign: 'center' });

  const docs = await frame(navRight, 'docs link', { layout: 'horizontal', gap: 8, crossAlign: 'center', padding: [8, 12] });
  await icon(docs, 'icon docs', 'doc', 20, T.muted);
  await txt(docs, 'label', 'Docs', { size: 14, weight: 'Medium', color: T.muted });

  const userPill = await frame(navRight, 'user pill', {
    layout: 'horizontal', gap: 12, crossAlign: 'center', padding: [6, 16], cornerRadius: 999, fills: T.userPill,
  });
  const userAv = await frame(userPill, 'avatar', {
    layout: 'horizontal', mainAlign: 'center', crossAlign: 'center', cornerRadius: 999, fills: T.avatar,
  }, { width: 32, height: 32 });
  await icon(userAv, 'icon user', 'user', 20, '#FFFFFF');
  await txt(userPill, 'user name', 'Edson', { size: 14, weight: 'SemiBold', color: T.strong });

  const sair = await frame(navRight, 'btn sair', {
    layout: 'horizontal', gap: 8, crossAlign: 'center', padding: [10, 16], cornerRadius: 8, fills: T.logoutFill,
  });
  await icon(sair, 'icon logout', 'logout', 20, '#FFFFFF');
  await txt(sair, 'label', 'Sair', { size: 14, weight: 'Medium', color: '#FFFFFF' });

  /* 02 Hero ------------------------------------------------------------ */
  const secHero = await frame(root, '02 Hero', { layout: 'vertical', padding: [24, 0] }, { width: CONTENT_W });
  const hero = await frame(secHero, 'hero card', {
    layout: 'horizontal', mainAlign: 'spaceBetween', crossAlign: 'center', gap: 24,
    padding: 32, cornerRadius: 16, fills: T.heroPaint, sizingH: 'fill',
  });
  const heroTx = await frame(hero, 'hero text', { layout: 'vertical', gap: 12, sizingH: 'fill' });
  await txt(heroTx, 'hero title', 'Olá, Edson! \u{1F44B}', { size: 36, weight: 'Bold', color: '#FFFFFF' });
  await txt(heroTx, 'hero subtitle', 'Gerencie suas contas Telegram e webhooks', { size: 18, weight: 'Regular', color: T.heroSub });
  const heroBadge = await frame(hero, 'hero badge', {
    layout: 'horizontal', mainAlign: 'center', crossAlign: 'center', cornerRadius: 999, fills: [S('#FFFFFF', 0.2)],
  }, { width: 96, height: 96 });
  await icon(heroBadge, 'icon phone', 'phone', 44, '#FFFFFF');

  /* 03 Stats ----------------------------------------------------------- */
  const secStats = await frame(root, '03 Stats', { layout: 'vertical', padding: [24, 0] }, { width: CONTENT_W });
  const statsRow = await frame(secStats, 'stats row', { layout: 'horizontal', gap: 24, crossAlign: 'max', sizingH: 'fill' });

  const STATS = [
    { name: 'Contas Telegram', value: '3', foot: '2 ativa(s)', i: 0 },
    { name: 'Webhooks Config', value: '2', foot: '1 pendente(s)', i: 1 },
    { name: 'Status', value: 'OK', foot: 'Sistema \u2713 ativo', i: 2 },
  ];

  for (const st of STATS) {
    const card = await frame(statsRow, 'card ' + st.name, {
      layout: 'vertical', gap: 0, cornerRadius: 16, fills: T.cardFill, sizingH: 'fill',
      ...(T.cardStroke ? { strokes: [S(T.cardStroke)], strokeWeight: 1, strokeAlign: 'inside' } : { effects: T.cardEffect }),
    });
    const body = await frame(card, 'card body', { layout: 'horizontal', gap: 20, crossAlign: 'center', padding: 24, sizingH: 'fill' });
    const box = await frame(body, 'icon box', {
      layout: 'horizontal', mainAlign: 'center', crossAlign: 'center', cornerRadius: 12, fills: T.icons[st.i],
    }, { width: 56, height: 56 });
    await icon(box, 'icon', ['phone', 'link', 'check'][st.i], 28, '#FFFFFF');
    const meta = await frame(body, 'card meta', { layout: 'vertical', gap: 4 });
    await txt(meta, 'label', st.name, { size: 14, weight: 'Medium', color: T.muted });
    await txt(meta, 'value', st.value, { size: 24, weight: 'Bold', color: T.strong });
    const strip = await frame(card, 'card strip', {
      layout: 'horizontal', crossAlign: 'center', padding: [12, 24], sizingH: 'fill', fills: T.strips[st.i],
    });
    await txt(strip, 'foot', st.foot, { size: 12, weight: 'SemiBold', color: T.stripText[st.i] });
  }

  /* 04 Contas ---------------------------------------------------------- */
  const secList = await frame(root, '04 Contas', { layout: 'vertical', padding: [24, 0, 32, 0] }, { width: CONTENT_W });
  const panel = await frame(secList, 'panel', {
    layout: 'vertical', gap: 0, cornerRadius: 16, fills: T.cardFill, sizingH: 'fill',
    ...(T.cardStroke ? { strokes: [S(T.cardStroke)], strokeWeight: 1, strokeAlign: 'inside' } : { effects: T.cardEffect }),
  });

  const head = await frame(panel, 'panel header', {
    layout: 'horizontal', mainAlign: 'spaceBetween', crossAlign: 'center', gap: 16,
    padding: 24, sizingH: 'fill', strokes: [S(T.navStroke)], strokeBottomWeight: 1, strokeWeight: 0, strokeAlign: 'inside',
  });
  const headLeft = await frame(head, 'header titles', { layout: 'vertical', gap: 4 });
  await txt(headLeft, 'panel title', 'Contas Telegram', { size: 24, weight: 'Bold', color: T.strong });
  await txt(headLeft, 'panel subtitle', 'Gerencie suas contas vinculadas', { size: 14, weight: 'Regular', color: T.muted });

  const cta = await frame(head, 'btn adicionar', {
    layout: 'horizontal', gap: 8, crossAlign: 'center', padding: [12, 24], cornerRadius: 12, fills: T.cta,
  });
  await icon(cta, 'icon plus', 'plus', 20, '#FFFFFF');
  await txt(cta, 'label', 'Adicionar Conta', { size: 16, weight: 'Bold', color: '#FFFFFF' });

  const SESSIONS = [
    { last4: '4832', name: 'Conta Principal', phone: '+55 11 98765-4832', active: true, hooks: 2 },
    { last4: '1097', name: 'Suporte Vendas', phone: '+55 11 98888-1097', active: false, hooks: 0 },
    { last4: '7742', name: 'Marketing', phone: '+55 11 97777-7742', active: true, hooks: 0 },
  ];

  for (const [i, s] of SESSIONS.entries()) {
    if (i > 0) {
      const sep = await frame(panel, 'divider', { layout: 'horizontal', sizingH: 'fill' }, { width: CONTENT_W, height: 1 });
      await setProps({ ids: [sep], props: { fills: [S('#F1F5F9')] } });
    }
    const row = await frame(panel, 'row ' + s.name, {
      layout: 'horizontal', mainAlign: 'spaceBetween', crossAlign: 'center', gap: 24, padding: 24, sizingH: 'fill',
    });
    const left = await frame(row, 'account info', { layout: 'horizontal', gap: 16, crossAlign: 'center', sizingH: 'fill' });
    const av = await frame(left, 'avatar', {
      layout: 'horizontal', mainAlign: 'center', crossAlign: 'center', cornerRadius: 999, fills: T.avatar,
    }, { width: 56, height: 56 });
    await txt(av, 'digits', s.last4, { size: 20, weight: 'Bold', color: '#FFFFFF' });

    const info = await frame(left, 'account meta', { layout: 'vertical', gap: 4, sizingH: 'fill' });
    const nameRow = await frame(info, 'name row', { layout: 'horizontal', gap: 8, crossAlign: 'center' });
    await txt(nameRow, 'name', s.name, { size: 16, weight: 'SemiBold', color: T.strong });
    await icon(nameRow, 'icon rename', 'pencil', 16, '#9CA3AF');
    await txt(info, 'phone', s.phone, { size: 12, weight: 'Regular', color: T.muted });

    const badges = await frame(info, 'badges', { layout: 'horizontal', gap: 8, crossAlign: 'center' });
    await pill(T, badges, 'badge status', s.active ? 'Online' : 'Offline', s.active ? '#22C55E' : '#EF4444', s.active ? '#DCFCE7' : '#FEE2E2', s.active ? '#166534' : '#991B1B');
    await pill(T, badges, 'badge webhooks', s.hooks > 0 ? `${s.hooks} webhook${s.hooks > 1 ? 's' : ''}` : 'Sem webhook', null, s.hooks > 0 ? '#DBEAFE' : '#FEF3C7', s.hooks > 0 ? '#1E40AF' : '#92400E');

    const acts = await frame(row, 'account actions', { layout: 'horizontal', gap: 12, crossAlign: 'center' });
    const A = [
      { key: 'link', label: 'Webhooks', i: 0, disabled: false },
      { key: 'chat', label: 'Mensagens', i: 1, disabled: false },
      { key: 'send', label: 'Mensagem', i: 2, disabled: !s.active },
      { key: 'trash', label: 'Remover', i: 3, disabled: false },
    ];
    for (const a of A) {
      const c = T.actions[a.i];
      const btn = await frame(acts, 'btn ' + a.label, {
        layout: 'horizontal', gap: 8, crossAlign: 'center', padding: [8, 16], cornerRadius: 8,
        fills: [], strokes: [S(c.stroke)], strokeWeight: 1, strokeAlign: 'inside',
        ...(a.disabled ? { opacity: 0.5 } : {}),
      });
      await icon(btn, 'icon ' + a.label, a.key, 16, c.icon);
      await txt(btn, 'label', a.label, { size: 14, weight: 'Medium', color: c.text });
    }
  }

  await flushIcons();
  return root;
}

(async () => {
  const a = await buildDashboard(3200, THEMES.atual);
  const b = await buildDashboard(4800, THEMES.flat);
  await saveFile({ path: SRC });
  for (const [id, name] of [[a, 'dashboard-atual'], [b, 'dashboard-flat']]) {
    await runCommand({
      command: 'file.export',
      params: { ids: [id], format: 'png', scale: 2, path: `D:/repos/telegram-account-webhook/docs/design/${name}.png` },
    });
  }
  console.log('OK atual=' + a + ' flat=' + b);
})().catch((e) => { console.error('ERR', e && e.message ? e.message : e); process.exit(1); });