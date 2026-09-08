import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';

const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';
const tesseractPath = 'C:/Program Files/Tesseract-OCR';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';

// ---------------------------------------------------------------------------
// Per-game knowledge registry (controls, boot/win/death markers, movement policy)
// Search-learning fills gaps: the backend fetches how-to text and can pass
// startKeysHint / winMarkersHint / strategy pixels into cfg.
// ---------------------------------------------------------------------------
const GAME_REGISTRY = {
  'dig-dug': {
    startKeys: ['X', 'Enter', '5', '1'],
    titleMarkers: [/1\s*PLAYER/i, /2\s*PLAYERS/i, /NAMCO/i],
    gameplayMarkers: [],
    winMarkers: [/ROUND\s*2/i, /LEVEL\s*2/i, /STAGE\s*2/i, /CONGRAT/i],
    deadMarkers: [/GAME\s*OVER/i],
    strategy: 'dig-dug',
    fallbackUrls: [
      'https://arcadespot.com/game/dig-dug/',
      'https://www.retrogames.cc/embed/21051-dig-dug-japan.html',
      'https://www.retrogames.cc/nes-games/dig-dug-japan.html',
      'https://www.retrogames.cc/embed/33379-dig-dug-rev-2.html',
    ],
  },
  'pac-man': {
    startKeys: ['5', '1', 'Enter', 'X', 'Z'],
    titleMarkers: [/PLAYER\s*ONE/i, /NAMCO/i, /1\s*UP/i, /INSERT\s*COIN/i],
    winMarkers: [/LEVEL\s*2/i, /STAGE\s*2/i, /ROUND\s*2/i],
    deadMarkers: [/GAME\s*OVER/i],
    strategy: 'pacman',
  },
  'galaga': {
    startKeys: ['5', '1', 'Enter', 'X', 'Z'],
    titleMarkers: [/INSERT\s*COIN/i, /1\s*PLAYER/i, /NAMCO/i],
    winMarkers: [/STAGE\s*2/i, /AREA\s*2/i, /ROUND\s*2/i],
    deadMarkers: [/GAME\s*OVER/i],
    strategy: 'galaga',
  },
  'mario': {
    startKeys: ['Enter', 'X', 'Z'],
    titleMarkers: [/PRESS\s*START/i, /WORLD/i, /MARIO/i],
    winMarkers: [/WORLD\s*2/i, /LEVEL\s*2/i],
    deadMarkers: [/GAME\s*OVER/i],
    strategy: 'mario',
  },
};

const STRATEGIES = {
  'dig-dug': ['ArrowLeft','ArrowLeft','X','ArrowLeft','ArrowLeft','ArrowDown','ArrowRight','ArrowRight','ArrowRight','X','ArrowLeft','ArrowLeft','ArrowDown','ArrowRight','X','ArrowRight','ArrowUp','ArrowLeft','X','ArrowDown','ArrowDown','X','ArrowRight','ArrowRight','X','ArrowUp','ArrowLeft','ArrowLeft','X'],
  'pacman': ['ArrowLeft','ArrowUp','ArrowRight','ArrowRight','ArrowDown','ArrowRight','ArrowUp','ArrowUp','ArrowLeft','ArrowDown','ArrowRight','ArrowLeft','ArrowUp','ArrowLeft','ArrowDown','ArrowRight','ArrowUp','ArrowRight','ArrowLeft','ArrowLeft'],
  'galaga': ['ArrowLeft','ArrowRight','X','Z','ArrowLeft','ArrowRight','Z','X','ArrowLeft','ArrowRight','X','Z','ArrowLeft','ArrowRight','Z','X'],
  'mario': ['ArrowRight','ArrowRight','X','ArrowRight','ArrowRight','ArrowUp','ArrowRight','ArrowRight','X','ArrowDown','ArrowRight','ArrowRight'],
  'arcade': ['ArrowLeft','ArrowDown','ArrowRight','ArrowUp','X','Z','ArrowLeft','ArrowDown','ArrowRight','ArrowUp','X','Z'],
};

function loadConfig() {
  const cfgPath = process.argv[2];
  if (!cfgPath || !fs.existsSync(cfgPath)) throw new Error('usage: node web_agent.mjs <config.json>');
  return JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
}

function buildState(cfg) {
  return {
    running: true,
    steps: 0,
    win: false,
    dead: false,
    started: false,
    mode: cfg.mode || 'game',
    device: cfg.device || 'web-agent',
    url: (cfg.game && cfg.game.url) || (cfg.task && cfg.task.url) || '',
    goal: cfg.goal || '',
    log: [],
    lastOcr: '',
    round: null,
    ts: 0,
  };
}

function say(state, m) { state.log.push(String(m)); console.log(m); }

async function ocrOfFile(state, png) {
  try {
    const env = { ...process.env, PATH: `${tesseractPath};${process.env.PATH || ''}` };
    const out = execFileSync(venvPy, [ocrPy, png], { env, encoding: 'utf8', timeout: 25000 });
    const m = out.match(/TEXT=([^\n]*)/);
    return m ? m[1].trim() : '';
  } catch (e) { return ''; }
}

async function perceive(state, page, clip, tag) {
  const png = path.join(tmp, `view_${tag}.png`);
  try {
    const shot = await page.screenshot({ clip: clip ? { x: clip.x, y: clip.y, width: clip.width, height: clip.height } : undefined });
    fs.writeFileSync(png, shot);
  } catch (e) {
    try { fs.writeFileSync(png, await page.screenshot()); } catch (e2) { return { text: '', error: String(e2) }; }
  }
  const text = await ocrOfFile(state, png);
  return { png, text, width: clip ? clip.width : 0, height: clip ? clip.height : 0 };
}

async function blobsOfFile(state, png) {
  try {
    const arg = png || path.join(tmp, 'view_play.png');
    const out = execFileSync(venvPy, ['C:/Users/trist/gemini-voice-assistant/dd_blobs.py', arg], { encoding: 'utf8', timeout: 20000 });
    const j = JSON.parse(out.trim());
    return j || null;
  } catch (e) { return null; }
}

// Vision-based steering for Dig Dug: prefers a target enemy and closes distance,
// pumping when roughly lined up. Returns a key for pressKey.
function visionKey(b, prevDir) {
  if (!b) return prevDir || 'ArrowLeft';
  const px = b.player && b.player.length ? b.player[0] : null;
  let enemies = b.enemy || [];
  if (!px) return prevDir || 'ArrowLeft';
  // nearest enemy by distance
  let target = null, best = Infinity;
  for (const e of enemies) {
    const d = Math.hypot(e.x - px.x, e.y - px.y);
    if (d < best) { best = d; target = e; }
  }
  if (!target) return prevDir || 'ArrowLeft';
  const dx = target.x - px.x, dy = target.y - px.y;
  const aligned = Math.abs(dx) < 8 || Math.abs(dy) < 8;
  if (aligned && best < 22) return 'X'; // pump
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? 'ArrowRight' : 'ArrowLeft';
  return dy > 0 ? 'ArrowDown' : 'ArrowUp';
}

function matchMarkers(text, markers) {
  if (!markers || !markers.length) return false;
  return markers.some((r) => r instanceof RegExp ? r.test(text) : text.toLowerCase().includes(String(r).toLowerCase()));
}

function roundFromText(text) {
  const m = text.match(/ROUND\s*([0-9]+)|LEVEL\s*([0-9]+)|STAGE\s*([0-9]+)|AREA\s*([0-9]+)|WORLD\s*([0-9]+)/i);
  if (!m) return null;
  return m.slice(1).find((v) => v !== undefined);
}

// ---------------------------------------------------------------------------
// GAME MODE
// ---------------------------------------------------------------------------
async function runVisionSearch(state, cfg, browser, page, { useSim, bootClip, pressKey, pressBtn, canvas, startKeys, titleMarkers, winMarkers, deadMarkers, strategy, keys, maxSteps }) {
  const g = cfg.game || {};
  let clip = bootClip;
  let started = state.started;

  // emulator liveness / browser crash survival: if the page or the EJS canvas
  // disappears mid-run, reload -> rebind -> boot back to gameplay automatically.
  const alive = async () => {
    try {
      for (const frame of page.frames()) {
        const ok = await frame.evaluate(() => {
          try { return !!(window.EJS_emulator && window.EJS_emulator.gameManager && document.querySelector('canvas')); } catch (e) { return false; }
        }).catch(() => false);
        if (ok) return true;
      }
      return false;
    } catch (e) { return false; }
  };
  const revive = async () => {
    state.attempts = (state.attempts || 1) + 1;
    say(state, `emulator lost (game closed) — reviving attempt ${state.attempts}`);
    try { await page.goto(g.__activeUrl || g.url, { waitUntil: 'domcontentloaded', timeout: 60000 }); } catch (e) { say(state, `revive goto failed: ${e.message.slice(0, 80)}`); return false; }
    await page.waitForTimeout(4000);
    try {
      const host2 = ((g.__activeUrl || g.url) || '').split('/')[2] || '';
      if (/arcadepot|arcadespot/i.test(host2)) {
        const playBtn = page.locator('a:text("Play"), button:text("Play"), a:text("Play Game"), button:text("Play Game"), .as-play-col').first();
        if (await playBtn.count()) await playBtn.click({ timeout: 6000 });
      }
    } catch (e) {}
    await page.waitForTimeout(9000);
    for (let i = 0; i < 40; i++) {
      const got = await frameEval(page, () => { try { return !!(window.EJS_emulator && document.querySelector('canvas.ejs_canvas')); } catch (e) { return false; } }).catch(() => false);
      if (got) break;
      await page.waitForTimeout(2000);
    }
    const sim = await bindEJS(page);
    clip = cachedFrameBox(page);
    if (!sim || !clip) { say(state, 'revive: no EJS/canvas after reload'); return false; }
    for (let b2 = 0; b2 < 10; b2++) {
      await pressKey(startKeys[b2 % startKeys.length], 400).catch(() => {});
      await pressKey('X', 350).catch(() => {});
      await page.waitForTimeout(1200);
      const rc = await perceive(state, page, clip, 'revive');
      if (!titleMarkers.length || !matchMarkers(rc.text, titleMarkers)) { started = true; say(state, `revived: gameplay reached (attempt ${state.attempts})`); return true; }
    }
    say(state, 'revive: boot timed out');
    return false;
  };

// frame capture + entity diff helpers (module-level venvPy/tmp)
  const shot = async (clip, name) => {
    const png = path.join(tmp, `${name}.png`);
    try {
      const shotBuf = await page.screenshot({ clip: clip ? { x: clip.x, y: clip.y, width: clip.width, height: clip.height } : undefined });
      fs.writeFileSync(png, shotBuf);
      if (name.startsWith('base_') || name.startsWith('play_')) {
        for (const f of fs.readdirSync(tmp)) {
          if ((f.startsWith('base_') || f.startsWith('play_')) && f !== `${name}.png`) { try { fs.unlinkSync(path.join(tmp, f)); } catch (e) {} }
        }
      }
      return png;
    } catch (e) { return null; }
  };
  const diffOf = async (basePng, afterPng) => {
    try {
      const out = execFileSync(venvPy, ['C:/Users/trist/gemini-voice-assistant/dd_diff.py', basePng, afterPng], { encoding: 'utf8', timeout: 20000 });
      return JSON.parse(out.trim());
    } catch (e) { return null; }
  };

// --- BOOT (same as runGame). No fast-forward: on EJS 4.x it freezes frames
  // and paints a "Fast-Forward. = ..." overlay that pollutes OCR.
  let boot = 0;
  while (boot < 16) {
    const see = await perceive(state, page, clip, 'boot');
    state.lastOcr = see.text;
    const onTitle = titleMarkers.length ? matchMarkers(see.text, titleMarkers) : false;
    say(state, `boot[${boot}] "${see.text.slice(0, 60)}" title=${onTitle}`);
    if (!onTitle && see.text.trim() && boot > 1) { state.started = true; started = true; break; }
    await pressKey(startKeys[boot % startKeys.length], 400).catch(() => {});
    await pressKey('X', 350).catch(() => {});
    await page.waitForTimeout(1200);
    boot++;
  }
  if (!state.started) { say(state, 'BOOT FAILED'); return; }
  say(state, 'GAME STARTED — survival autopilot (play through round 1)');

  // Autopilot parameters: hand-overridden in cfg.game.autopilot, or seeded from
  // a gameplay-research notes file (written by mode:'research') so later runs
  // start from what was learned instead of hardcoded defaults.
  const notes = loadResearchNotes(g.researchNotes, g.registry);
  const AP = {
    danger: (g.autopilot && g.autopilot.danger) || (notes ? notes.danger : null) || 48,
    chase: (g.autopilot && g.autopilot.chase) || (notes ? notes.chase : null) || 200,
    align: (g.autopilot && g.autopilot.align) || (notes ? notes.align : null) || 26,
    wander: (g.autopilot && g.autopilot.wander) || (notes ? notes.wander : null) || ['ArrowRight', 'ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowLeft', 'ArrowUp'],
  };
  if (notes) say(state, `research notes loaded: danger=${AP.danger} chase=${AP.chase} align=${AP.align} wander=[${AP.wander.join(',')}]`);

  // --- SURVIVAL AUTOPILOT
  // Each step: snapshot player+enemy positions (dd_diff on a single frame),
  // then move to stay alive: FLEE when an enemy is too close, PUMP when lined up
  // and in range, CHASE only from a safe distance, otherwise scan. The game plays
  // forward continuously (no loadState rewinds), so a life actually progresses
  // toward clearing the round. On death we re-boot from the title and keep trying
  // until ROUND 2 (level-1 clear) or maxSteps.
  const snapshot = async (png) => (png ? await diffOf(png, png) : null);
  // dd_diff returns 0..100 normalized coords; convert to canvas pixels so the
  // danger/chase/pump thresholds match the sprite and tunnel sizing.
  const toPx = (p) => (clip ? { x: (p.x / 100) * clip.width, y: (p.y / 100) * clip.height } : p);
  const dist = (a, b) => (a && b ? Math.hypot(a.x - b.x, a.y - b.y) : Infinity);
  const nearestFoe = (px, foes) => {
    let t = null, m = Infinity;
    for (const f of foes || []) { const d = dist(px, f); if (d < m) { m = d; t = f; } }
    return { foe: t, d: m };
  };
  const aligned = (px, foe) => (px && foe ? Math.abs(px.x - foe.x) < AP.align || Math.abs(px.y - foe.y) < 30 : false);
  const fleeKey = (px, foes) => {
    const cands = [['ArrowLeft', -16, 0], ['ArrowRight', 16, 0], ['ArrowUp', 0, -16], ['ArrowDown', 0, 16]];
    let bestKey = 'ArrowLeft', bestScore = -Infinity;
    for (const [k, dx, dy] of cands) {
      let m = Infinity;
      for (const f of foes || []) m = Math.min(m, Math.hypot(px.x + dx - f.x, px.y + dy - f.y));
      if (m > bestScore) { bestScore = m; bestKey = k; }
    }
    return bestKey;
  };
  const towardKey = (px, foe) => { const dx = foe.x - px.x, dy = foe.y - px.y; return Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'ArrowRight' : 'ArrowLeft') : (dy > 0 ? 'ArrowDown' : 'ArrowUp'); };
  // player P1 score from HUD text (OCR reads 0 as 'o', 1 as 'i'/'l')
  const scoreOf = (t) => { const m = (t || '').replace(/[oO]+/g, '0').replace(/[iIl|]/g, '1').match(/SCORE\s+([0-9]{3,7})\s+([0-9]{2,7})/i); return m ? parseInt(m[2], 10) : null; };
  // live AI HUD overlay: injected into the host page (top frame). Fixed to the
// viewport bottom-left (below the 960x480 canvas) so it never enters the OCR
// clip and is always visible in the game window.
  const hud = async (lines) => {
    if (!page || page.isClosed()) return;
    await page.evaluate(({ lines }) => {
      try {
        let el = document.getElementById('jester-hud');
        if (!el) {
          el = document.createElement('div');
          el.id = 'jester-hud';
          el.style.cssText = 'position:fixed;z-index:2147483647;left:8px;bottom:8px;width:300px;background:rgba(0,0,0,0.88);color:#7CFF7C;font:12px/1.5 Consolas,monospace;padding:8px 10px;border:1px solid #00ff88;border-radius:8px;pointer-events:none;opacity:0.97;white-space:pre;box-shadow:0 2px 12px rgba(0,255,136,0.2);';
          (document.body || document.documentElement).appendChild(el);
        }
        el.textContent = lines.join('\n');
      } catch (e) {}
    }, { lines }).catch(() => {});
  };

  state.steps = 0;
  state.trace = state.trace || [];
  state._hudChecked = false;

  // ---- tabular Q-learner (persists across lives via state.q; saved to the
  // state file by main(), so experience accumulates session over session) ----
  // State = (nearest-enemy distance bucket, aligned?) -> 10 states.
  // Actions = 4 directions + PUMP. Reward: +60 per confirmed kill (enemy cluster
  // count dropped), +3 for pumping an aligned target, +2 for pushing it into a
  // corner, +1 per step closes the gap, score jumps (+1 per 10 pts), -4 for
  // touching danger, -80 terminal on death, +60 on a life-clear.
  const KILL = 60;
  const KILL_RANGE = 70;
  if (!state.q) state.q = {};
  state._eps = state._eps != null ? state._eps : (g.learner?.eps ?? 0.25);
  state._lastScore = state._lastScore != null ? state._lastScore : null;
  state._pendingR = state._pendingR || 0;
  state._lastR = state._lastR || 0;
  const L_LR = g.learner?.lr ?? 0.5;
  const L_G = g.learner?.gamma ?? 0.9;
  const L_EPS_MIN = g.learner?.epsMin ?? 0.1;
  const distB = (d) => (d < 36 ? 0 : d < 95 ? 1 : d < 165 ? 2 : d < 260 ? 3 : 4);
  const stateIdx = (d, al) => distB(d) * 2 + (al ? 1 : 0);
  const ACTS = { 'ArrowUp': 0, 'ArrowDown': 1, 'ArrowLeft': 2, 'ArrowRight': 3, 'X': 4 };
  const qGet = (s, a) => Number(state.q[`${s}|${ACTS[a]}`] || 0);
  const qSet = (s, a, v) => { state.q[`${s}|${ACTS[a]}`] = Math.round(v * 10) / 10; };
  const maxQ = (s) => { let m = 0; for (let a = 0; a < 5; a++) m = Math.max(m, Number(state.q[`${s}|${a}`] || 0)); return m; };
  const qPick = (s) => {
    // epsilon-greedy over the direction actions
    if (Math.random() < state._eps) return ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'][Math.floor(Math.random() * 4)];
    let best = 'ArrowUp', bestV = -Infinity;
    for (const k of ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight']) { const v = qGet(s, k); if (v > bestV) { bestV = v; best = k; } }
    return best;
  };
  const deathPunish = () => { if (lastS >= 0 && lastA >= 0) qSet(lastS, lastA, qGet(lastS, lastA) + L_LR * (-80 - qGet(lastS, lastA))); };
  let lastS = -1, lastA = -1, prevFoe = 0, lastD = null;

  while (state.steps < maxSteps && !state.win) {
    // survive page/emulator crashes so a life isn't killed by infrastructure
    if (!(await alive().catch(() => false))) {
      const ok = await revive();
      if (!ok) { say(state, 'revive failed — stopping'); break; }
      state.started = true; started = true;
    }
    const png = await shot(clip, `play_${state.steps}`);
    const ent = png ? await snapshot(png) : null;
    const entPx = ent && ent.basePlayer ? toPx(ent.basePlayer) : null;
    const foesPx = (ent && ent.baseEnemies ? ent.baseEnemies : []).map(toPx);
    let key = 'ArrowRight', note = 'NOPOS';
    if (entPx) {
      const { foe, d } = nearestFoe(entPx, foesPx);
      const isAlign = aligned(entPx, foe);
      const sNow = stateIdx(d, isAlign);
      let r = 0;
      // confirmed kill: an enemy cluster vanished between frames
      if (prevFoe > 0 && foesPx.length < prevFoe) { r += KILL; state.kills = (state.kills || 0) + 1; say(state, `KILL #${state.kills} at step ${state.steps}: ${prevFoe}->${foesPx.length} foes`); }
      // approach shaping: reward actions that closed the gap, punish widening
      if (lastD != null && foe) { const shrink = lastD - d; r += shrink > 0 ? 1 : shrink < -2 ? -1 : 0; }
      lastD = d;
      if (d < AP.danger) { key = fleeKey(entPx, foesPx); note = `FLEE d=${d | 0}`; r -= 4; }
      else if (isAlign && d < KILL_RANGE) {
        // squeeze: alternate pump / push the enemy along the tunnel so it fills up
        if (state.steps % 3 === 2) { key = towardKey(entPx, foe); note = `PRESS d=${d | 0}`; r += 2; }
        else { key = 'X'; note = `PUMP d=${d | 0}`; r += 3; }
      } else if (foe && d < AP.chase) { key = qPick(sNow); note = `LEARN d=${d | 0} Q(${sNow},${key})=${qGet(sNow, key)}`; }
      else if (foe) { key = towardKey(entPx, foe); note = `SEARCH d=${d | 0}`; r += 1; }
      else { key = AP.wander[state.steps % AP.wander.length]; note = 'SCAN'; }
      // learn: the reward just earned belongs to the action chosen LAST step.
      // This step's r is topped up by any score jump observed at the last OCR.
      const rFull = r + Number(state._pendingR || 0);
      state._pendingR = 0;
      if (lastS >= 0 && lastA >= 0) qSet(lastS, lastA, qGet(lastS, lastA) + L_LR * (rFull + L_G * maxQ(sNow) - qGet(lastS, lastA)));
      state._lastR = rFull;
      lastS = sNow; lastA = ACTS[key];
      state._eps = Math.max(L_EPS_MIN, state._eps * 0.9995);
    } else { note = 'NOPOS'; }
    state.trace.push({ i: state.steps, k: key, n: note, d: entPx ? nearestFoe(entPx, foesPx).d | 0 : null, t: Date.now() });
    await pressKey(key, key === 'X' ? 420 : 240).catch(() => {});
    await page.waitForTimeout(60);
    prevFoe = foesPx.length;
    state.steps += 1;

    // --- AI HUD (data marks): live overlay + periodic stats file for dashboards
    if (state.steps % 2 === 0) {
      const dNow = entPx ? nearestFoe(entPx, foesPx).d | 0 : null;
      const hudObj = {
        game: g.registry || 'game', attempt: state.attempts || 1, life: (state.lives || 0) + 1,
        lifeBudget: g.lifeBudget || 20, step: state.steps, round: state.round || 0,
        action: note, kills: state.kills || 0, score: state._lastScore ?? 0,
        qStates: Object.keys(state.q || {}).length, eps: (state._eps ?? 0),
        foes: foesPx.length, nearest: dNow, reward: Math.round(state._lastR || 0),
        alive: started, src: cfg.stateFile || '', ts: Date.now(),
      };
      state.hud = hudObj;
      await hud([
        `JESTER AI  ${hudObj.game.toUpperCase()}`,
        `ATTEMPT ${hudObj.attempt}   LIFE ${hudObj.life}/${hudObj.lifeBudget}`,
        `STEP ${hudObj.step}   ROUND ${hudObj.round}${hudObj.alive ? '' : '  (booting)'}`,
        `ACTION ${hudObj.action}`,
        `KILLS ${hudObj.kills}   SCORE ${hudObj.score}`,
        `FOES ${hudObj.foes}   NEAREST ${hudObj.nearest ?? '-'}px`,
        `Q ${hudObj.qStates} STATES   EPS ${hudObj.eps.toFixed(2)}`,
        `LAST REWARD ${hudObj.reward >= 0 ? '+' : ''}${hudObj.reward}`,
      ]);
      if (state.steps % 10 === 0) { try { fs.writeFileSync(path.join(tmp, 'hud_stats.json'), JSON.stringify(hudObj)); } catch (e) {} }
    }

    if (state.steps % 5 === 0) {
      const see = await perceive(state, page, clip, 'play');
      state.lastOcr = see.text;
      const rr = see.text.match(/ROUND\s*([0-9]+)/i);
      if (rr) state.round = rr[1];
      // score jumps are a dense progress signal: reward the action that caused them
      const sc = scoreOf(see.text);
      if (sc != null && state._lastScore != null) {
        const delta = sc - state._lastScore;
        if (delta >= 50 && state._lastScore >= 0) { const bonus = Math.min(24, Math.round(delta / 10)); state._pendingR = (state._pendingR || 0) + bonus; say(state, `SCORE ${state._lastScore}->${sc} (+${delta}) reward +${bonus}`); }
      }
      if (sc != null) state._lastScore = sc;
      // once per life, prove the HUD overlay is alive in the browser
      if (!state._hudChecked) {
        state._hudChecked = true;
        const h = await page.evaluate(() => {
          const el = document.getElementById('jester-hud');
          if (!el) return 'NO_HUD_ELEMENT';
          const r = el.getBoundingClientRect();
          return `HUD ${Math.round(r.width)}x${Math.round(r.height)} @${Math.round(r.left)},${Math.round(r.top)} "${el.textContent.slice(0, 28)}"`;
        }).catch((e) => `HUD_EVAL_ERR:${String(e).slice(0, 40)}`);
        say(state, `[hud-check] ${h}`);
      }
      say(state, `step=${state.steps} ${note} round=${state.round} kills=${state.kills || 0} score=${state._lastScore ?? '-'} ocr="${see.text.slice(0, 42)}"`);
      if (winMarkers.length && matchMarkers(see.text, winMarkers)) { if (lastS >= 0 && lastA >= 0) qSet(lastS, lastA, qGet(lastS, lastA) + L_LR * (60 - qGet(lastS, lastA))); state.win = true; say(state, '*** WIN: level-1 clear (ROUND 2 reached) ***'); break; }
      if (deadMarkers.length && matchMarkers(see.text, deadMarkers)) say(state, 'GAME OVER screen seen — re-booting from title');
      if (state.started && titleMarkers.length && matchMarkers(see.text, titleMarkers)) {
        // life lost: propagate the terminal punishment into the learner
        deathPunish(); lastS = -1; lastA = -1; prevFoe = 0; lastD = null;
        state.lives = (state.lives || 0) + 1;
        if (state.lives >= (g.lifeBudget || 20)) { say(state, `life budget reached (${state.lives}) with ${state.kills || 0} kills — fresh game needed`); break; }
        if (g.researchStop) { say(state, `research: life ended at step ${state.steps}`); break; }
        // all lives spent → title back. Re-boot a fresh game and keep trying.
        state.attempts = (state.attempts || 1) + 1;
        say(state, `died — attempt ${state.attempts - 1} over, re-booting to keep trying`);
        state.started = false; started = false;
        state.steps = 0; // fresh life = fresh time budget
        state.round = null;
        for (let b2 = 0; b2 < 8 && !state.started; b2++) {
          await pressKey(startKeys[b2 % startKeys.length], 400).catch(() => {});
          await pressKey('X', 350).catch(() => {});
          await page.waitForTimeout(1100);
          const rc = await perceive(state, page, clip, 'reboot');
          if (!titleMarkers.length || !matchMarkers(rc.text, titleMarkers)) { state.started = true; started = true; say(state, `attempt ${state.attempts} started`); break; }
        }
        if (!state.started) { say(state, 're-boot failed — pausing'); await page.waitForTimeout(2000); }
      }
    }
  }
  const qEntries = Object.keys(state.q).length;
  if (state.hud) { try { state.hud.action = note; fs.writeFileSync(path.join(tmp, 'hud_stats.json'), JSON.stringify({ ...state.hud, done: true, ts: Date.now() })); } catch (e) {} }
  say(state, `DONE steps=${state.steps} win=${state.win} round=${state.round} attempts=${state.attempts || 1} kills=${state.kills || 0} score=${state._lastScore ?? '-'} qEntries=${qEntries} eps=${state._eps.toFixed(2)}`);
}

async function runGame(state, cfg, browser, page) {
  const g = cfg.game || {};
  const reg = GAME_REGISTRY[g.registry] || {};
  const isCanvas = g.canvas !== false; // EJS embeds produce a 960x480 canvas; plain web games vary
  const startKeys = (g.startKeysHint && g.startKeysHint.length ? g.startKeysHint : reg.startKeys) || ['Enter', 'X', '5', '1'];
  const titleMarkers = (g.titleMarkersHint && g.titleMarkersHint.length ? g.titleMarkersHint : reg.titleMarkers) || [];
  const winMarkers = (g.winMarkersHint && g.winMarkersHint.length ? g.winMarkersHint : reg.winMarkers) || [/LEVEL\s*2/i, /ROUND\s*2/i];
  const deadMarkers = (g.deadMarkersHint && g.deadMarkersHint.length ? g.deadMarkersHint : reg.deadMarkers) || [/GAME\s*OVER/i];
  const strategy = (g.strategyHint || reg.strategy || g.strategy || 'arcade');
  const keys = STRATEGIES[strategy] || STRATEGIES['arcade'];
  const maxSteps = g.maxSteps || cfg.maxSteps || 260;

  // Sim-input mode: EJS cores expose Module.cwrap('simulate_input', 'null',
  // ['number','number','number']) = (port, button, state). Keyboard events are
  // unreliable inside stacked/embedded pages; simulate_input bypasses all focus
  // and reaches the core directly.
  let useSim = await bindEJS(page);
  const SIMBTN = { 'ArrowUp': 4, 'ArrowDown': 5, 'ArrowLeft': 6, 'ArrowRight': 7, 'X': 8, 'A': 8, 'Space': 8, 'Z': 0, 'B': 0, 'Enter': 3, 'NumpadEnter': 3, 'Return': 3, 'Shift': 2, '5': 3, '1': 3 };
  const BUTTON_NAMES = { 4: 'ArrowUp', 5: 'ArrowDown', 6: 'ArrowLeft', 7: 'ArrowRight', 8: 'X', 0: 'Z', 3: 'Enter' };
  const pressKey = (k, holdMs) => {
    const btn = SIMBTN[k];
    if (useSim && btn !== undefined) {
      return frameEval(page, (b) => { try { window.__SIM3(0, b, 1); } catch (e) {} }, btn)
        .then(() => page.waitForTimeout(holdMs || 300))
        .then(() => frameEval(page, (b) => { try { window.__SIM3(0, b, 0); } catch (e) {} }, btn));
    }
    return page.keyboard.down(k).then(() => page.waitForTimeout(holdMs || 300)).then(() => page.keyboard.up(k));
  };
  const pressBtn = (btn, holdMs) => {
    return frameEval(page, (b) => { try { window.__SIM3(0, b, 1); } catch (e) {} }, btn)
      .then(() => page.waitForTimeout(holdMs || 300))
      .then(() => frameEval(page, (b) => { try { window.__SIM3(0, b, 0); } catch (e) {} }, btn));
  };

  say(state, `GAME ${g.url}` + (g.registry ? ` (${g.registry})` : '') + (useSim ? ' [sim-input]' : ' [keyboard]'));
  // failover: if the primary host won't resolve/load (site down, DNS outage), try
  // registry-level mirrors so the session survives instead of dying outright.
  const fallbackUrls = [...(reg.fallbackUrls || []), ...(g.fallbackUrls || [])].filter((u, i, a) => u && u !== g.url && a.indexOf(u) === i);
  let navigated = null;
  for (const u of [g.url, ...fallbackUrls]) {
    try {
      await page.goto(u, { waitUntil: 'domcontentloaded', timeout: 60000 });
      navigated = u;
      break;
    } catch (e) {
      const host = (u || '').split('/')[2] || u;
      say(state, `goto failed ${host}: ${String(e.message || e).split('\n')[0].slice(0, 110)}`);
      await page.waitForTimeout(1500);
    }
  }
  if (!navigated) { say(state, 'ALL hosts failed to load'); state.error = 'goto failed on all hosts'; return; }
  const host = (navigated || g.url).split('/')[2] || '';
  if (navigated !== g.url) { try { g.__activeUrl = navigated; } catch (e) {} say(state, `using fallback host: ${host}`); }
  await page.waitForTimeout(5000);

  // The primary arcade site needs a Play CTA click (arcadepot starts on the title;
  // arcadespot autoloads the game beneath a play overlay). EmulatorJS mirrors (the
  // fallbacks) boot the ROM directly, so only click on the arcade hosts.
  const arcadeHost = /arcadepot|arcadespot/i.test(host);
  if (arcadeHost) {
    const selectors = [
      'a:text("Play")', 'button:text("Play")', 'a:text("Play Game")', 'button:text("Play Game")',
      '.as-play-col', 'a:text("Play Game")',
    ];
    let clicked = false;
    for (const sel of selectors) {
      const playBtn = page.locator(sel).first();
      try {
        if (await playBtn.count()) { await playBtn.click({ timeout: 6000 }); clicked = true; say(state, `CLICKED CTA: ${sel}`); break; }
      } catch (e) {}
    }
    if (clicked) state.clicked = true;
    await page.waitForTimeout(isCanvas ? 9000 : 4000);
    try {
      const fsBtn = page.locator('.as-game-fullscreen, button[id*=fullscreen], [class*=fullscreen]').first();
      if (await fsBtn.count()) { await fsBtn.click({ timeout: 5000 }); state.fullscreen = true; await page.waitForTimeout(1200); }
    } catch (e) {}
  } else {
    await page.waitForTimeout(3000);
  }

  // wait until the EJS emulator object + canvas actually exist across any frame
  // (mirror embeds fetch the ROM before the core is created; stepping too early
  // yields no sim, and the emulator may live in an iframe)
  let gotEJS = false;
  for (let i = 0; i < 40; i++) {
    for (const frame of page.frames()) {
      gotEJS = await frame.evaluate(() => {
        try { return !!(window.EJS_emulator && document.querySelector('canvas.ejs_canvas')); } catch (e) { return false; }
      }).catch(() => false);
      if (gotEJS) break;
    }
    if (gotEJS) break;
    await page.waitForTimeout(2000);
  }
  if (gotEJS) say(state, 'EJS + canvas present after load');

  let canvas = null;
  if (isCanvas) {
    const c = page.locator('canvas.ejs_canvas, canvas#nes, canvas').first();
    if (await c.count()) canvas = c;
  }

  // Sim-input + GameManager bindings must be set AFTER the page/emulator loads
  // (EJS_emulator only exists post-boot). Recompute now that the page is up.
  {
    const sim = await bindEJS(page);
    if (sim) useSim = sim;
    if (useSim) say(state, 'SIM+GM bound (EJS loaded)');
  }

  await page.bringToFront().catch(() => {});

  // Vision-search mode: use GameManager save/load + fast-forward to branch and
  // retry, learning which actions maximize survival/enemy-kills. Requires EJS.
  say(state, `DBG vision=${g.vision} useSim=${useSim}`);
  if (g.vision && useSim) {
    const gmReady = await frameEval(page, () => { try { return !!(window.__GM && window.__GM.getState && window.__GM.loadState); } catch (e) { return false; } });
    if (gmReady) {
      say(state, 'VISION-SEARCH mode (save/load + FF)');
      let bootClip = cachedFrameBox(page) || (canvas ? await box(page, canvas) : null);
      state.attempts = 1;
      await runVisionSearch(state, cfg, browser, page, {
        useSim, bootClip, pressKey, pressBtn, canvas,
        startKeys, titleMarkers, winMarkers, deadMarkers, strategy, keys, maxSteps,
      });
      return;
    } else {
      say(state, 'VISION-SEARCH unavailable (no gameManager state API) — falling back to play loop');
    }
  }

  // --- BOOT: probe start keys until the title screen leaves gameplay appears
  let boot = 0;
  const bootClip = cachedFrameBox(page) || (canvas ? await box(page, canvas) : null);
  while (boot < 16) {
    const see = await perceive(state, page, bootClip, 'boot');
    state.lastOcr = see.text;
    const onTitle = titleMarkers.length ? matchMarkers(see.text, titleMarkers) : false;
    say(state, `boot[${boot}] "${see.text.slice(0, 60)}" title=${onTitle}`);
    if (!onTitle && see.text.trim()) {
      if (boot > 1) { state.started = true; say(state, 'GAME STARTED (boot left title)'); break; }
    }
    await pressKey(startKeys[boot % startKeys.length], 400).catch(() => {});
    await pressKey('X', 350).catch(() => {});
    await page.waitForTimeout(1200);
    boot++;
  }
  if (!state.started) say(state, `boot exhausted (${boot})`);

  // --- PLAY LOOP with vision verify
  let prevText = '';
  let idleStreak = 0;
  let rounds = new Set();
  state.attempts = 1;
  while (state.steps < maxSteps && !state.win && !state.dead) {
    state.steps += 1;
    let k;
    if (g.vision) {
      const seeB = await perceive(state, page, bootClip, 'play');
      state.lastOcr = seeB.text;
      const bl = await blobsOfFile(state, seeB.png);
      k = visionKey(bl, state._prevDir || 'ArrowLeft');
      if (k !== 'X') state._prevDir = k;
    } else {
      k = keys[state.steps % keys.length];
    }
    await pressKey(k, (strategy === 'pacman' || strategy === 'mario') ? 220 : 300).catch(() => {});
    await page.waitForTimeout(120);

    if (state.steps % 6 === 0) {
      const see = await perceive(state, page, bootClip, 'play');
      state.lastOcr = see.text;
      const r = roundFromText(see.text);
      if (r && !rounds.has(r)) { rounds.add(r); state.round = r; say(state, `ROUND/LEVEL ${r}`); }
      if (matchMarkers(see.text, winMarkers)) { state.win = true; say(state, '*** WIN: level-clear marker detected ***'); break; }
      if (matchMarkers(see.text, deadMarkers)) { state.dead = true; say(state, 'GAME OVER'); break; }
      // If we were in gameplay and the title screen came back, the player died:
      // auto-restart a fresh attempt instead of stopping.
      if (state.started && titleMarkers.length && matchMarkers(see.text, titleMarkers)) {
        state.attempts = (state.attempts || 1) + 1;
        say(state, `attempt ${state.attempts - 1} ended (title back) — restarting life`);
        state.started = false;
        // Mini boot: press START until the title actually leaves again.
        for (let b2 = 0; b2 < 8 && !state.started; b2++) {
          await pressKey(startKeys[0], 400).catch(() => {});
          await pressKey('Enter', 400).catch(() => {});
          await page.waitForTimeout(1100);
const rc = await perceive(state, page, clip, 'reboot');
          state.lastOcr = rc.text;
          if (!titleMarkers.length || !matchMarkers(rc.text, titleMarkers)) {
            state.started = true;
            say(state, `attempt ${state.attempts} started`);
            prevText = '';
            idleStreak = 0;
          }
        }
        if (!state.started) say(state, `restart boot failed after ${state.attempts}`);
      }
      const changed = see.text !== prevText;
      if (changed) idleStreak = 0; else idleStreak++;
      prevText = see.text;
      if (idleStreak >= 6) {
        say(state, `idle at ${state.steps} — re-boot attempt`);
        for (const kk of startKeys.slice(0, 2)) { await pressKey(kk, 400).catch(() => {}); await page.waitForTimeout(700); }
        idleStreak = 0;
      }
      if (state.steps % 30 === 0) say(state, `step ${state.steps} key=${k} "${see.text.slice(0, 50)}"`);
    }
  }
  say(state, `DONE steps=${state.steps} win=${state.win} dead=${state.dead} round=${state.round} attempts=${state.attempts}`);
}

// ---------------------------------------------------------------------------
// TASK MODE — generic web jobs: navigate, click by text/selector, type, read.
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// DIGGER MODE — custom canvas tunneling game (digger_game.html) driven through
// its __GG debug API (exact state, no OCR). Reuses the persisted Q-table +
// epsilon schedule (state.q / state._eps) so lessons survive across lives.
// State = (col, row, columns-fully-cleared bucket); action = one dig/move step.
// ---------------------------------------------------------------------------
async function runDigger(state, cfg, browser, page) {
  const g = cfg.game || {};
  let u = g.url || '';
  if (!/^(file|https?):/i.test(u) && /\.html$/i.test(u)) u = pathToFileURL(path.resolve(u)).href;
  const level = Number(g.level || (u.match(/[?&]level=(\d+)/) || [])[1]) || 3;
  const maxSteps = g.maxSteps || cfg.maxSteps || 400;
  const lifeBudget = g.lifeBudget || 4;
  const LR = 0.3, G = 0.95;
  const ACTS = ['left', 'right', 'up', 'down', 'dig']; // 0..4
  const COLS = 12, ROWS = 8, DIRT = 84;

  const q = state.q || (state.q = {});
  let eps = state._eps != null ? state._eps : 0.35;
  const qGet = (k) => Number(q[k] || 0);
  const qSet = (k, v) => { q[k] = v; };
  const key = (s, a) => `${s}|${a}`;
  const maxQ = (s) => { let m = 0; for (let a = 0; a < 5; a++) { const v = qGet(key(s, a)); if (v > m) m = v; } return m; };
  const actPick = (s) => (Math.random() < eps ? Math.floor(Math.random() * 5) : qArgmax(s));
  const qArgmax = (s) => { let best = 0, bv = -Infinity; for (let a = 0; a < 5; a++) { const v = qGet(key(s, a)); if (v > bv) { bv = v; best = a; } } return best; };
  const enc = (col, row) => `${col}|${row}|${Math.min(12, Math.floor(state._clearedNow / 7))}`;
  const encD = (st) => `${enc(st.col, st.row)}|${st.diggable ? 1 : 0}`;

  // deterministic "coach" policy: dig the current column to the top, descend its
  // shaft, walk the surface to the nearest unfinished column, repeat. The first
  // few episodes are coached (imitation); the learner still runs its own Q
  // updates on every coached transition, so the table is learned, not shipped.
  const tutor = (st) => {
    if (st.diggable) return ACTS.indexOf('dig');   // mid-shaft of unfinished column
    if (st.row === 0) return ACTS.indexOf('down'); // stood on the top: descend own shaft
    if (st.row === 7) {                            // surface: walk toward nearest work
      if (st.nextDx < 0) return ACTS.indexOf('left');
      if (st.nextDx > 0) return ACTS.indexOf('right');
    }
    return ACTS.indexOf('down');                   // mid-shaft of finished column: descend
  };

  const step = (a) => page.evaluate((a) => { if (a === 'dig') window.__GG.dig(); else if (a) window.__GG.input(a); return window.__GG.state(); }, a).catch(() => null);
  const gs = () => page.evaluate(() => window.__GG.state()).catch(() => null);

  // HUD overlay (local game page)
  const hud = async (lines) => {
    if (!page || page.isClosed()) return;
    await page.evaluate(({ lines }) => {
      try {
        let el = document.getElementById('jester-hud');
        if (!el) {
          el = document.createElement('div');
          el.id = 'jester-hud';
          el.style.cssText = 'position:fixed;z-index:2147483647;right:10px;top:10px;width:290px;background:rgba(0,0,0,0.88);color:#7CFF7C;font:12px/1.5 Consolas,monospace;padding:8px 10px;border:1px solid #00ff88;border-radius:8px;pointer-events:none;white-space:pre;';
          document.body.appendChild(el);
        }
        el.textContent = lines.join('\n');
      } catch (e) {}
    }, { lines }).catch(() => {});
  };

  // navigate with reload-on-death revive
  let tryNav = 0;
  while (tryNav < 3) {
    try {
      await page.goto(u, { waitUntil: 'load', timeout: 30000 });
      break;
    } catch (e) { tryNav++; await page.waitForTimeout(800); }
  }
  if (tryNav >= 3) { state.error = 'digger goto failed'; return; }
  for (let i = 0; i < 30; i++) {
    const ok = await page.evaluate(() => { try { return !!window.__GG; } catch (e) { return false; } }).catch(() => false);
    if (ok) break;
    await page.waitForTimeout(200);
  }
  await page.waitForTimeout(300);

  let prev = await gs(); if (!prev) { state.error = 'digger __GG unavailable'; return; }
  state._clearedNow = prev.cleared;
  state.episodes = (state.episodes || 0) + 1;
  let bestCleared = (state.bestCleared || 0);
  let bestScore = (state.bestScore || 0);
  const coach = state.episodes <= (g.coachEpisodes || 3);
  if (coach) { eps = Math.min(eps, 0.05); }

  say(state, `DIGGER level=${level} eps=${eps.toFixed(2)} qStates=${Object.keys(q).length} episode=${state.episodes}${coach ? ' [COACH]' : ''}`);
  hud(['JESTER AI  DIGGER-TUNNELER', `LEVEL ${level} · episode ${state.episodes}${coach ? ' · coach' : ''}`, '', 'step..clear..score' , '', `Q states: ${Object.keys(q).length}` , `eps: ${eps.toFixed(3)}`]);

  let terminal = null;
  while (state.steps < maxSteps) {
    state.steps += 1;
    const s = encD(prev);
    const a = coach ? tutor(prev) : actPick(s);
    const next = await step(ACTS[a]);
    if (!next) { say(state, `page dead at step ${state.steps} — reviving`); try { await page.goto(u, { waitUntil: 'load', timeout: 30000 }); } catch (e) {} for (let i = 0; i < 20; i++) { const ok = await page.evaluate(() => { try { return !!window.__GG; } catch (e) { return false; } }).catch(() => false); if (ok) break; await page.waitForTimeout(150); } prev = await gs(); if (!prev) break; state._clearedNow = prev.cleared; continue; }

    const newTiles = next.cleared - (state._clearedNow || 0);
    const beforeBucket = Math.floor((state._clearedNow || 0) / 7);
    const afterBucket = Math.floor(next.cleared / 7);
    let r = -0.05;                                       // tiny step cost (efficiency)
    if (newTiles > 0) r += 4 * newTiles;                 // +4 per freshly dug tile
    if (afterBucket > beforeBucket) r += 15;             // +15 per column finished
    if (next.row > prev.row) r += 1.5;                   // descending into own tunnel
    if (next.row === 7 && next.cleared < 84) r += 1;     // surface is the staging area
    if (next.won) r += 200;                              // level cleared
    if (next.over) r -= 30;                              // hit by enemy row

    // Q update (terminal on won/over)
    const s2 = encD(next);
    const target = r + (next.won || next.over ? 0 : G * maxQ(s2));
    const qv = qGet(key(s, a)) + LR * (target - qGet(key(s, a)));
    qSet(key(s, a), qv);
    state._clearedNow = next.cleared;

    if (newTiles > 0 || state.steps % 5 === 0) {
      say(state, `step=${state.steps} ${ACTS[a]} (${s}|${a}) r=${r.toFixed(1)} cleared=${next.cleared} score=${next.score} Q=${qv.toFixed(2)} eps=${eps.toFixed(3)}`);
    }
    if (state.steps % 10 === 0) {
      eps = Math.max(0.08, eps * 0.998); state._eps = eps;
      const lines = ['JESTER AI  DIGGER-TUNNELER', `LEVEL ${level} · episode ${state.episodes}`, `step ${state.steps} · cleared ${next.cleared}/${DIRT}`, `last action ${ACTS[a]} · r ${r.toFixed(1)}`, `Q(${s}|${a}) ${qv.toFixed(2)}`, `eps ${eps.toFixed(3)} · qStates ${Object.keys(q).length}`];
      hud(lines);
      try {
        fs.writeFileSync(path.join(tmp, 'hud_stats.json'), JSON.stringify({ game: 'digger', episode: state.episodes, step: state.steps, cleared: next.cleared, score: next.score, action: ACTS[a], reward: r, eps, qStates: Object.keys(q).length, won: next.won, over: next.over, ts: Date.now() }));
      } catch (e) {}
    }
    prev = next;
    if (next.won) { terminal = 'WON'; state.win = true; break; }
    if (next.over) { terminal = 'OVER'; break; }
  }

  bestCleared = Math.max(bestCleared, prev.cleared); state.bestCleared = bestCleared;
  bestScore = Math.max(bestScore, prev.score); state.bestScore = bestScore;
  state._eps = eps; state._lastScore = prev.score; state.score = prev.score;
  state.kills = prev.cleared; // tiles cleared as progress metric
  if (terminal === 'OVER') {
    state.lives = (state.lives || 1) + 1; state.dead = true;   // reward death via main retry cadence
  }
  say(state, `DIGGER DONE episode=${state.episodes} steps=${state.steps} cleared=${prev.cleared}/84 score=${prev.score} best=${bestCleared} terminal=${terminal || 'timeout'} qStates=${Object.keys(q).length} eps=${eps.toFixed(3)}`);
}

async function runTask(state, cfg, browser, page) {
  const t = cfg.task || {};
  const actions = t.actions || [];
  const maxSteps = t.maxSteps || cfg.maxSteps || 40;
  say(state, `TASK ${t.url || ''} (${actions.length} actions)`);
  if (t.url) { await page.goto(t.url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await page.waitForTimeout(2500); }

  for (const a of actions) {
    if (state.steps >= maxSteps) { say(state, 'max task steps reached'); break; }
    state.steps += 1;
    try {
      if (a.type === 'wait') { await page.waitForTimeout(a.ms || 2000); say(state, `wait ${a.ms || 2000}`); }
      else if (a.type === 'clickText') {
        const loc = page.locator(`text="${a.text}"`).first();
        if (await loc.count()) { await loc.click({ timeout: 8000 }); say(state, `clicked text "${a.text}"`); }
        else say(state, `NO TEXT "${a.text}"`);
      } else if (a.type === 'click') {
        const loc = page.locator(a.selector).first();
        if (await loc.count()) { await loc.click({ timeout: 8000 }); say(state, `clicked ${a.selector}`); }
        else say(state, `NO SEL ${a.selector}`);
      } else if (a.type === 'type') {
        const loc = page.locator(a.selector).first();
        if (await loc.count()) { await loc.fill(a.value || ''); say(state, `typed into ${a.selector}`); }
        else say(state, `NO SEL ${a.selector}`);
      } else if (a.type === 'press') { await page.keyboard.press(a.key); say(state, `pressed ${a.key}`); }
      else if (a.type === 'read') {
        const sel = a.selector || 'body';
        const loc = page.locator(sel).first();
        const txt = (await loc.count()) ? (await loc.innerText().catch(() => '')).slice(0, (a.max || 2000)) : '';
        const see = await perceive(state, page, await box(page, loc), 'read');
        state.lastOcr = see.text;
        say(state, `READ[${sel}] "${txt.replace(/\s+/g, ' ').slice(0, 300)}"`);
        if (a.saveKey) state[a.saveKey] = txt;
      } else if (a.type === 'goto') { await page.goto(a.url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await page.waitForTimeout(a.ms || 2000); say(state, `goto ${a.url}`); }
      else if (a.type === 'screenshot') { await perceive(state, page, null, 'task'); say(state, 'screenshot taken'); }
      if (a.verifyText) {
        const see = await perceive(state, page, null, 'verify');
        const hit = see.text.toLowerCase().includes(a.verifyText.toLowerCase());
        say(state, `VERIFY "${a.verifyText}" -> ${hit}`);
        if (!hit && a.stopIfMissing === true) { state.error = `verify failed: ${a.verifyText}`; break; }
      }
    } catch (e) { say(state, `ACT_ERR(${a.type}): ${e.message.slice(0, 120)}`); }
    await page.waitForTimeout(a.waitAfter || 600);
  }
  say(state, 'TASK DONE');
}

async function box(page, locator) {
  try { return (await locator.boundingBox()) || null; } catch (e) { return null; }
}

// EJS can run in the top page (arcadepot) OR inside a child frame (retrogames
// mirrors). Find the frame that owns a working simulator: EJS_emulator with a
// gameManager (getState/loadState) AND cwrap('simulate_input'). Returns the
// resident frame plus the canvas box in MAIN-page coordinates (frame-enabled
// locator.boundingBox handles cross-frame conversion).
const ejsBindings = new WeakMap(); // page -> { frame, frameBox }
async function detectEJS(page) {
  const frames = page.frames();
  for (const frame of frames) {
    try {
      const ok = await frame.evaluate(() => {
        try {
          const E = window.EJS_emulator;
          if (!E || !E.gameManager) return false;
          if (typeof E.Module?.cwrap !== 'function') return false;
          if (typeof E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']) !== 'function') return false;
          return !!(E.gameManager.getState && E.gameManager.loadState);
        } catch (e) { return false; }
      });
      if (!ok) continue;
      const c = frame.locator('canvas.ejs_canvas, canvas#nes, canvas').first();
      if (await c.count()) {
        const frameBox = await box(page, c);
        if (frameBox) return { frame, frameBox };
      }
      return { frame, frameBox: null };
    } catch (e) { /* frame detached — skip */ }
  }
  return null;
}

// Bind EJS simulate_input + GameManager (save/load/FF) into the owning frame's
// window. Idempotent; call after any reload. Also caches the canvas box.
async function bindEJS(page) {
  const ctx = await detectEJS(page).catch(() => null);
  if (ctx) {
    try {
      await ctx.frame.evaluate(() => {
        const E = window.EJS_emulator;
        window.__SIM3 = E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']);
        window.__GM = E.gameManager;
        window.__FF = (v) => { try { E.gameManager.toggleFastForward(v); } catch (e) {} };
      });
      ejsBindings.set(page, ctx);
      return true;
    } catch (e) { ejsBindings.delete(page); return false; }
  }
  ejsBindings.delete(page);
  return false;
}

// Evaluate a function in the frame that owns the EJS emulator (falls back to the
// top page). Used by all simulate_input / GameManager round-trips.
function frameEval(page, fn, arg) {
  const ctx = ejsBindings.get(page);
  const f = ctx && ctx.frame && !ctx.frame.isDetached() ? ctx.frame : page;
  return f.evaluate(fn, arg);
}
function cachedFrameBox(page) {
  const ctx = ejsBindings.get(page);
  return (ctx && ctx.frameBox) || null;
}

// ---------------------------------------------------------------------------
// Gameplay-research tool: "pre-learn" a game before the agent has to play it.
// Runs the autopilot across parameter variants and multiple lives, records how
// long each config survives, and writes a reusable notes file (researchNotes)
// that later game runs load to seed their autopilot. Works for any registry
// entry; for tasks the same loop can be pointed at runTask with a win marker.
function loadResearchNotes(researchNotes, registry) {
  if (!researchNotes) return null;
  try {
    const j = JSON.parse(fs.readFileSync(path.resolve(researchNotes), 'utf8'));
    if (registry && j && j.registry && j.registry !== registry) return null; // notes belong to another game
    return (j && j.params) || j || null;
  } catch (e) { return null; }
}

async function researchGame(state, cfg, browser, page) {
  const g = cfg.game || {};
  const reg = GAME_REGISTRY[g.registry] || {};
  const outFile = cfg.research?.outFile || path.join(tmp, 'research_notes.json');
  const sceneName = g.registry || g.url || 'game';
  const GRID = cfg.research?.grid || [
    { danger: 48, chase: 200, align: 26, wander: ['ArrowRight', 'ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowLeft', 'ArrowUp'] },
    { danger: 65, chase: 240, align: 28, wander: ['ArrowRight', 'ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowLeft', 'ArrowUp'] },
    { danger: 36, chase: 160, align: 20, wander: ['ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowLeft', 'ArrowUp', 'ArrowUp'] },
  ];
  const scenes = Math.max(1, cfg.research?.scenes || 2);
  const lifeCap = cfg.research?.maxSteps || 300;

  say(state, `--- RESEARCH ${sceneName}: ${GRID.length} configs x ${scenes} lives ---`);
  let best = null, bestScore = -Infinity;
  const results = [];
  for (let gi = 0; gi < GRID.length; gi++) {
    const params = GRID[gi];
    let survival = 0, wins = 0;
    for (let s = 0; s < scenes; s++) {
      const st = buildState(cfg);
      const cfg2 = { ...cfg, game: { ...g, autopilot: params, researchStop: true, maxSteps: lifeCap } };
      await runGame(st, cfg2, browser, page);
      const steps = st.steps > 0 ? st.steps : (st.win ? lifeCap : 0);
      survival += steps;
      if (st.win) wins += 1;
      say(state, `  cfg${gi + 1} life${s + 1}: steps=${st.steps} win=${st.win} round=${st.round} attempts=${st.attempts}`);
    }
    const mean = survival / scenes;
    const score = mean + wins * (lifeCap * 2); // winning a life is worth two full lives
    results.push({ ...params, meanSurvival: Math.round(mean), wins, score: Math.round(score) });
    if (score > bestScore) { bestScore = score; best = params; }
    say(state, `  cfg${gi + 1}: meanSurvival=${Math.round(mean)} wins=${wins} score=${Math.round(score)}`);
  }
  const notes = {
    registry: g.registry || null,
    url: g.url || null,
    ts: Date.now(),
    params: best,
    results,
    hint: 'best autopilot params from offline research; consumed via cfg.game.researchNotes',
  };
  try {
    fs.mkdirSync(path.dirname(outFile), { recursive: true });
    fs.writeFileSync(outFile, JSON.stringify(notes, null, 2));
  } catch (e) { say(state, `research notes write failed: ${e.message.slice(0, 80)}`); }
  say(state, `--- RESEARCH DONE → ${outFile} (best: danger=${best.danger} chase=${best.chase} align=${best.align}) ---`);
  state.research = notes;
  state.win = bestScore > 0 && results.some((r) => r.wins > 0);
}

// ---------------------------------------------------------------------------
async function main() {
  const cfg = loadConfig();
  const stateFile = cfg.stateFile || path.join(tmp, 'web_agent_state.json');
  let mem = {};
  let q = {};
  let eps = null;
  try { const prev = JSON.parse(fs.readFileSync(stateFile, 'utf8')); if (prev && prev.mem) mem = prev.mem; if (prev && prev.q) q = prev.q; if (prev && prev._eps != null) eps = prev._eps; } catch (e) {}
  const state = buildState(cfg);
  state.mem = mem;
  if (Object.keys(q).length) state.q = q;              // resume learned Q-table
  if (eps != null) state._eps = eps;                   // resume exploration schedule
  // startup hygiene: drop leftover screenshots from previous runs
  try { for (const f of fs.readdirSync(tmp)) if (/^(view|base|dd|diff|ev|boot|reboot|revive)_/i.test(f) && f.endsWith('.png')) fs.unlinkSync(path.join(tmp, f)); } catch (e) {}
  // Browser crash survival: if the emulator host kills the page/context mid-run
  // (ad-heavy mirrors, OOM, RA errors), relaunch a fresh page and re-run the game
  // loop instead of ending the session. Both runVisionSearch's revive() and this
  // top-level retry protect against "the game keeps closing".
  // Learning loop: each attempt that ends in a REAL death (state.dead) feeds a
  // punishment signal back into `state.mem` (persisted to stateFile), so later
  // lives play differently. We keep re-booting lives until we win or maxRetries
  // runs out — i.e., the agent keeps learning until it actually dies and loses.
  const maxRetries = Math.max(1, cfg.maxRetries || 3);
  let lastBrowser = null;
  let didWin = false;
  let didDie = false;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    let browser = null;
    let page = null;
    try {
      browser = await chromium.launch({
        headless: cfg.headless === true,
        executablePath: chromePath,
        args: ['--start-fullscreen', '--disable-extensions'],
      });
      lastBrowser = browser;
      page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
      page.on('pageerror', (e) => say(state, `PAGE_ERR: ${e.message.slice(0, 100)}`));
      page.on('close', () => say(state, 'PAGE closed (will revive on next liveness check)'));
      page.on('crash', () => say(state, 'PAGE crashed (will revive on next liveness check)'));
      if (attempt > 1) say(state, `--- learning attempt #${attempt} (fresh life) ---`);
      state.dead = false; state.win = false; state.started = false; state.steps = 0;
      if (cfg.mode === 'game') {
        if ((cfg.game && /digger[-_ ]game/i.test(cfg.game.url || '')) || (cfg.game && cfg.game.registry === 'digger')) {
          await runDigger(state, cfg, browser, page);
          if (state.win) {
            didWin = true;
            if (!(cfg.game && cfg.game.keepGoing)) { break; }
            state.win = false; // keep going: prove the learned policy plays on its own
          }
          if (state.dead) didDie = true;
        } else {
          await runGame(state, cfg, browser, page);
          if (state.win) { didWin = true; break; }
          if (state.dead) didDie = true;
        }
      }
      else if (cfg.mode === 'task') await runTask(state, cfg, browser, page);
      else if (cfg.mode === 'research') {
        await researchGame(state, cfg, browser, page);
        state.dead = true; // a full grid scan is one unit of work; don't re-run it
        state.trace = (state.trace || []).slice(-20); // keep state file small
      } else throw new Error('mode must be game, task or research');
      // persist this attempt's memory immediately so a crash can't lose it
      fs.writeFileSync(stateFile, JSON.stringify(state));
      if (state.win) { didWin = true; break; }
      if (state.dead) didDie = true;
      // if we neither won nor really died (e.g. infrastructure aborted), retry
      if (!didDie && state.error) say(state, 'no clean death this attempt — retrying');
      if (cfg.mode === 'research') break; // a grid scan is one unit of work, not a learning loop
    } catch (e) {
      const msg = String(e.message || e).slice(0, 180);
      say(state, `AGENT_ERR (attempt ${attempt}): ${msg}`);
      state.error = msg;
      // a crashed attempt still learned things (Q/kills/score): persist now so
      // the next fresh life continues from this experience.
      try { fs.writeFileSync(stateFile, JSON.stringify(state)); } catch (e2) {}
    } finally {
      try { if (page) await page.waitForTimeout(1000).catch(() => {}); } catch (e2) {}
      try { if (browser) await browser.close().catch(() => {}); } catch (e2) {}
      await new Promise((r) => setTimeout(r, 1500));
    }
  }
  state.win = didWin;
  if (didDie && !didWin) say(state, `memories after ${maxRetries} lost lives: ${JSON.stringify(state.mem)}`);
  say(state, `learning after run: lives=${state.lives || 1} kills=${state.kills || 0} score=${state._lastScore ?? '-'} qEntries=${Object.keys(state.q || {}).length} eps=${(state._eps || 0).toFixed(2)}`);
  try { if (lastBrowser && !lastBrowser.isConnected()) lastBrowser = null; } catch (e2) {}
  state.running = false;
  state.ts = Date.now();
  fs.writeFileSync(stateFile, JSON.stringify(state));
}

main();