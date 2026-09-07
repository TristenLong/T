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
    titleMarkers: [/1\s*PLAYER/i, /NAMCO/i, /1UP/i, /HI[-\s]*SCORE/i],
    gameplayMarkers: [],
    winMarkers: [/ROUND\s*2/i, /LEVEL\s*2/i, /STAGE\s*2/i, /CONGRAT/i],
    deadMarkers: [/GAME\s*OVER/i],
    strategy: 'dig-dug',
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

  say(state, `GAME ${g.url}` + (g.registry ? ` (${g.registry})` : ''));
  await page.goto(g.url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);

  // Click the obvious play/launch CTA
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game"), a:text("Play"), button:text("Play"), [id*=play]').first();
  try {
    if (await playBtn.count()) { await playBtn.click({ timeout: 8000 }); state.clicked = true; say(state, 'CLICKED PLAY CTA'); }
  } catch (e) {}
  await page.waitForTimeout(isCanvas ? 9000 : 4000);

  // fullscreen the emulator embed if present
  try {
    const fsBtn = page.locator('.as-game-fullscreen, button[id*=fullscreen], [class*=fullscreen]').first();
    if (await fsBtn.count()) { await fsBtn.click({ timeout: 5000 }); state.fullscreen = true; await page.waitForTimeout(1200); }
  } catch (e) {}

  let canvas = null;
  if (isCanvas) {
    const c = page.locator('canvas.ejs_canvas, canvas#nes, canvas').first();
    if (await c.count()) canvas = c;
  }
  await page.bringToFront().catch(() => {});

  // --- BOOT: probe start keys until the title screen leaves gameplay appears
  let boot = 0;
  const bootClip = canvas ? await box(page, canvas) : null;
  while (boot < 16) {
    const see = await perceive(state, page, bootClip, 'boot');
    state.lastOcr = see.text;
    const onTitle = titleMarkers.length ? matchMarkers(see.text, titleMarkers) : false;
    const looksPlay = !onTitle && see.text.trim().length > 0;
    say(state, `boot[${boot}] "${see.text.slice(0, 60)}" title=${onTitle}`);
    if (!titleMarkers.length && see.text.trim()) { } // no title markers defined: always try keys
    if (!onTitle && see.text.trim()) {
      if (boot > 1) { state.started = true; say(state, 'GAME STARTED (boot left title)'); break; }
    }
    const k = startKeys[boot % startKeys.length];
    await page.keyboard.press(k);
    await page.waitForTimeout(1500);
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
    const k = keys[state.steps % keys.length];
    await page.keyboard.down(k);
    await page.waitForTimeout((strategy === 'pacman' || strategy === 'mario') ? 220 : 300);
    await page.keyboard.up(k);
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
        await page.keyboard.press(startKeys[0]);
        await page.waitForTimeout(1400);
        await page.keyboard.press(startKeys[0]);
        await page.waitForTimeout(1400);
        const recheck = await perceive(state, page, bootClip, 'reboot');
        state.lastOcr = recheck.text;
        if (!titleMarkers.length || !matchMarkers(recheck.text, titleMarkers)) {
          state.started = true;
          say(state, `attempt ${state.attempts} started`);
          prevText = '';
          idleStreak = 0;
          continue;
        }
      }
      const changed = see.text !== prevText;
      if (changed) idleStreak = 0; else idleStreak++;
      prevText = see.text;
      if (idleStreak >= 6) {
        say(state, `idle at ${state.steps} — re-boot attempt`);
        for (const kk of startKeys.slice(0, 2)) { await page.keyboard.press(kk); await page.waitForTimeout(700); }
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

// ---------------------------------------------------------------------------
async function main() {
  const cfg = loadConfig();
  const state = buildState(cfg);
  const stateFile = cfg.stateFile || path.join(tmp, 'web_agent_state.json');
  const browser = await chromium.launch({
    headless: cfg.headless === true,
    executablePath: chromePath,
    args: ['--start-fullscreen', '--disable-extensions'],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on('pageerror', (e) => say(state, `PAGE_ERR: ${e.message.slice(0, 100)}`));
  try {
    if (cfg.mode === 'game') await runGame(state, cfg, browser, page);
    else if (cfg.mode === 'task') await runTask(state, cfg, browser, page);
    else throw new Error('mode must be game or task');
  } catch (e) {
    say(state, `AGENT_ERR: ${e.message.slice(0, 250)}`);
    state.error = e.message.slice(0, 500);
  } finally {
    state.running = false;
    state.ts = Date.now();
    fs.writeFileSync(stateFile, JSON.stringify(state));
    await page.waitForTimeout(1500);
    await browser.close();
  }
}

main();