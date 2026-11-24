const fs = require('fs'), path = require('path'), cp = require('child_process'), url = require('url');
const P = __dirname;
const pkg = JSON.parse(fs.readFileSync(path.join(P, 'package.json'), 'utf8'));
const H = process.env.HOME || '/work/maison';
const C = (n) => 'CANARI_' + n + '_7f3ac9';

// Budget global : le harnais tue a TMO (120 s). Tout ce qui suit doit tenir en 75 s,
// sinon le vrai main ne serait jamais charge — defaut releve par la revue (196 s
// d'execSync bloquants > 90 s de run).
// Horloge REELLE du harnais, capturee avant tout decalage : sans elle, decaler
// l'horloge du paquet epuise notre propre budget et le vrai code n'est jamais
// charge (mesure : reste_ms=0 des les premieres millisecondes).
const VRAI_NOW_MS = Date.now.bind(Date);
const T0 = VRAI_NOW_MS();
const BUDGET = 75000;
// Trace de progression : sans elle, « main non chargé » et « jamais atteint » sont
// indistinguables — c'est exactement le faux négatif silencieux de la revue.
const trace = (etape, extra) => {
  // Le paquet n'est PAS ramené après le run : la trace doit atterrir dans /work/out,
  // seul répertoire copié (sinon « où s'est-il arrêté » reste invisible).
  const cibles = ['/work/out/_sbx_etat.jsonl', require('path').join(__dirname, '_sbx_etat.jsonl')];
  try { console.error('[trace] ' + etape + ' ' + JSON.stringify({ t: Date.now() - T0, ...extra })); } catch (e) {}
  for (const c of cibles) { try { fs.appendFileSync(c, JSON.stringify({ etape, t: Date.now() - T0, ...extra }) + '\n'); break; } catch (e) {} }
};
trace('demarrage', { pkg: pkg.name, type: pkg.type || 'commonjs' });
const reste = () => Math.max(0, BUDGET - (VRAI_NOW_MS() - T0));

function mk(p, s) { try { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, s); } catch (e) {} }
mk(path.join(H, '.npmrc'), '//registry.npmjs.org/:_authToken=' + C('NPM') + '\n');
mk(path.join(H, '.ssh', 'id_ed25519'), '-----BEGIN OPENSSH PRIVATE KEY-----\n' + C('SSH') + '\n');
mk(path.join(H, '.aws', 'credentials'), '[default]\naws_access_key_id=' + C('AWS') + '\n');
mk(path.join(H, '.config', 'gh', 'hosts.yml'), 'oauth_token: ' + C('GH') + '\n');
mk(path.join(H, '.docker', 'config.json'), '{"auths":{"r":{"auth":"' + C('DOCKER') + '"}}}');
mk(path.join(H, '.kube', 'config'), 'token: ' + C('KUBE') + '\n');
mk(path.join(H, '.gitconfig'), '[user]\n\tname = ' + C('GIT') + '\n');
mk(path.join(H, '.env'), 'SECRET=' + C('ENV') + '\n');
mk(path.join(H, '.config', 'gcloud', 'application_default_credentials.json'), '{"refresh_token":"' + C('GCLOUD') + '"}');
mk(path.join(H, 'wa-session', 'creds.json'), JSON.stringify({ me: { id: '33600000000:1@s.whatsapp.net' }, noise: {}, routingInfo: C('WA') }));
mk(path.join(H, 'Cookies'), C('COOKIE'));
mk(path.join(H, '.bash_history'), 'ssh root@' + C('HIST') + '\n');

// Plafonner aussi les modules natifs : `require('node:timers')` échappait au patch
// des globales (relevé en audit, puis vérifié : un setInterval de 3 jours passait).
const Module = require('module');
const _load = Module._load;
Module._load = function (demande, ...reste) {
  const m = _load.apply(this, [demande, ...reste]);
  if (demande === 'timers' || demande === 'node:timers') {
    for (const f of ['setTimeout', 'setInterval']) {
      const vrai = m[f];
      if (typeof vrai === 'function') m[f] = (fn, ms, ...a) => vrai(fn, typeof ms === 'number' && ms > 1500 ? 1500 : ms, ...a);
    }
  }
  // timers/promises : setTimeout ET setInterval ET scheduler.wait (audit, tour 2)
  if (demande === 'timers/promises' || demande === 'node:timers/promises') {
    for (const f of ['setTimeout', 'setInterval', 'scheduler']) {
      if (f === 'scheduler' && m.scheduler && typeof m.scheduler.wait === 'function') {
        const vrai = m.scheduler.wait.bind(m.scheduler);
        m.scheduler.wait = (ms, ...a) => vrai(typeof ms === 'number' && ms > 1500 ? 1500 : ms, ...a);
      } else if (typeof m[f] === 'function') {
        const vrai = m[f];
        m[f] = (ms, ...a) => vrai(typeof ms === 'number' && ms > 1500 ? 1500 : ms, ...a);
      }
    }
  }
  return m;
};
// Horloge decalee : plafonner les delais ne suffit pas si la charge utile compare
// des dates (`if (Date.now() - installe > 30 jours)`). SBX_OFFSET_JOURS decale
// l'horloge vue par le paquet ; le harnais, lui, garde la vraie pour ses mesures.
let OFFSET = Number(process.env.SBX_OFFSET_JOURS || 0) * 86400000;
// Le harnais lance le paquet avec un environnement controle : une variable
// d'environnement est perdue. Le decalage vient donc d'un FICHIER depose a cote
// du pilote (mesure : sonde d'horloge muette avec l'env, allumee avec le fichier).
try {
  const o = JSON.parse(fs.readFileSync(path.join(__dirname, '_sbx_offset.json'), 'utf8'));
  if (o.jours) OFFSET = Number(o.jours) * 86400000;
  if (o.installe_ms) process.env.SBX_INSTALLE_MS = String(o.installe_ms);
} catch (e) {}
if (OFFSET) {
  const VRAI_NOW = Date.now.bind(Date);
  const VraieDate = Date;
  Date.now = () => VRAI_NOW() + OFFSET;
  global.Date = class extends VraieDate {
    constructor(...a) { if (a.length === 0) { super(VRAI_NOW() + OFFSET); } else { super(...a); } }
    static now() { return VRAI_NOW() + OFFSET; }
  };
  trace('horloge_decalee', { jours: OFFSET / 86400000 });
}

const vraiST = global.setTimeout, vraiSI = global.setInterval;
const plafond = (ms) => (typeof ms === 'number' && ms > 1500 ? 1500 : ms);
global.setTimeout = function (f, ms, ...a) { return vraiST(f, plafond(ms), ...a); };
global.setInterval = function (f, ms, ...a) { return vraiSI(f, plafond(ms), ...a); };

// 1. scripts de cycle de vie — 8 s chacun, jamais au-dela du budget
for (const k of ['preinstall', 'install', 'postinstall', 'prepare']) {
  const c = (pkg.scripts || {})[k];
  if (!c || reste() < 9000) continue;
  try { cp.execSync(c, { cwd: P, stdio: 'ignore', timeout: Math.min(8000, reste() - 2000), env: { ...process.env, HOME: H } }); } catch (e) {}
}

// 1 bis. scripts de cycle de vie des DEPENDANCES : `require()` ne les execute
// jamais et l'installation les avait desactives. Trou releve en audit.
try {
  const listeDep = JSON.parse(fs.readFileSync(path.join(P, '_sbx_deps_scripts.json'), 'utf8'));
  let faits = 0;
  for (const d of listeDep) {
    if (faits >= 20 || reste() < 20000) break;
    try {
      cp.execSync(d.script, { cwd: path.join(P, 'node_modules', d.nom), stdio: 'ignore', timeout: 3000, env: { ...process.env, HOME: H } });
      faits++;
    } catch (e) { faits++; }
  }
  trace('cycle_vie_deps', { scripts: listeDep.length, faits });
} catch (e) {}

// 2. bins — 4 s, trois au plus (avant : 8 x 12 s = 96 s)
const bins = pkg.bin ? (typeof pkg.bin === 'string' ? [pkg.bin] : Object.values(pkg.bin)) : [];
for (const b of bins.slice(0, 3)) {
  for (const arg of ['--help', '--version']) {
    if (reste() < 12000) break;
    try { cp.execSync(`node ${JSON.stringify(path.resolve(P, b))} ${arg}`, { cwd: H, stdio: 'ignore', timeout: 4000, env: { ...process.env, HOME: H } }); } catch (e) {}
  }
}

trace('cycle_vie_fini', { reste_ms: reste() });

// 3. vrai point d'entree — jamais le pilote lui-meme, ESM gere par import()
function candidats() {
  // Node IGNORE `main` quand `exports` existe : lister `main`/`index.js` d'abord
  // faisait charger un leurre benin et rater la charge utile (revue hy4, BLOQUANT).
  const extraits = [];
  const extraire = (v) => {
    if (typeof v === 'string') extraits.push(v.replace(/^\.\//, ''));
    else if (v && typeof v === 'object') Object.values(v).forEach(extraire);
  };
  if (pkg.exports) extraire(pkg.exports['.'] !== undefined ? pkg.exports['.'] : pkg.exports);
  const secours = [pkg._sbx_main, 'index.js', 'dist/index.js', 'lib/index.js', 'index.mjs'];
  const ordre = pkg.exports ? [...extraits, ...secours] : [...secours, ...extraits];
  const vus = new Set();
  return ordre.filter((r) => {
    if (!r || r.includes('_sbx_scenario3') || vus.has(r)) return false;
    vus.add(r);
    return fs.existsSync(path.resolve(P, r));
  }).slice(0, 6);
}

(async () => {
  const cands = candidats();
  const charges = [];
  const pilotes = [];
  for (const r of cands) {
    if (reste() < 10000) break;
    const abs = path.resolve(P, r);
    const esm = pkg.type === 'module' || r.endsWith('.mjs');
    try {
      const mod = esm ? await import(url.pathToFileURL(abs).href) : require(abs);
      charges.push(r); pilotes.push(mod);
    } catch (e) {}
  }
  trace('main', { charge: charges.join(','), esm: pkg.type === 'module', candidats: cands.length, reste_ms: reste() });

  const SESSION = path.join(H, 'wa-session');
  const fakeAuth = () => ({ creds: JSON.parse(fs.readFileSync(path.join(SESSION, 'creds.json'), 'utf8')), keys: {} });
  const piloter = (v) => {
    if (typeof v !== 'function') return;
    try {
      const r = v(SESSION, { auth: fakeAuth(), printQRInTerminal: false, logger: { level: 'silent', child: () => ({ level: 'silent', child: () => ({}) }) } });
      if (r && typeof r.then === 'function') r.catch(() => {});
      if (r && r.ev && r.ev.emit) {
        r.ev.emit('connection.update', { connection: 'open', isOnline: true });
        r.ev.emit('messages.upsert', { messages: [{ key: { remoteJid: '1@s.whatsapp.net' }, message: { conversation: C('MSG') } }], type: 'notify' });
        r.ev.emit('creds.update', {});
      }
    } catch (e) {}
  };
  for (const mod of pilotes) {
    if (!mod) continue;
    try { for (const k of Object.keys(mod)) piloter(mod[k]); } catch (e) {}
    if (typeof mod === 'function') piloter(mod);
  }
  trace('pilote', { modules: pilotes.length });
  vraiST(() => process.exit(0), Math.min(15000, Math.max(3000, reste())));
})();
