import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';
import path from 'path';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const maxSteps = parseInt(process.argv[3] || '260', 10);
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';
const tesseractPath = 'C:/Program Files/Tesseract-OCR';

const log = [];
const state = {
  running: true, steps: 0, win: false, dead: false, started: false,
  mode: 'ejs-driver', url, goal: process.argv[4] || 'win the first level',
  log, lastOcr: '', round: null, fullscreen: false, clicked: false,
  verifier: (process.env.JESTER_VERIFIER || 'node-playwright'), ts: 0,
};

function say(m) { log.push(String(m)); console.log(m); }

async function ocrCrop(page, canvas, tag) {
  try {
    const box = await canvas.boundingBox();
    if (!box) return '';
    const shot = await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } });
    const png = path.join(tmp, `game_${tag}.png`);
    fs.writeFileSync(png, shot);
    const env = { ...process.env, PATH: `${tesseractPath};${process.env.PATH || ''}` };
    const out = execFileSync(venvPy, [ocrPy, png], { env, encoding: 'utf8', timeout: 25000 });
    const m = out.match(/TEXT=([^\n]*)/);
    return m ? m[1].trim() : '';
  } catch (e) {
    return '';
  }
}

function textMarkers(t) {
  const up = /1\s*UP|1UP/i.test(t);
  const hi = /HI[-\s]*SCORE|HISCO/i.test(t);
  const players = /PLAYER/i.test(t);
  const round = t.match(/ROUND|RQND|R0ND|RN|ROND/i);
  const round2 = /ROUND\s*2|RQND\s*2|ROUND2|R0ND/i.test(t) || /L[E&]*V[E&]*L\s*2/.test(t) || /STAGE\s*2/.test(t);
  const gameOver = /GAME\s*OVER|GAMEOVER/i.test(t);
  const insertCoin = /INSERT\s*COIN|PUSH/i.test(t);
  return { up, hi, players, round: round ? round[0] : null, round2, gameOver, insertCoin, alive: t.length > 0 };
}

const pattern = [
  'ArrowLeft', 'ArrowLeft', 'X', 'ArrowLeft', 'ArrowLeft', 'ArrowLeft',
  'ArrowDown', 'ArrowRight', 'ArrowRight', 'ArrowRight', 'ArrowRight', 'ArrowRight', 'X',
  'ArrowLeft', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'X',
  'ArrowRight', 'ArrowRight', 'ArrowUp', 'ArrowLeft', 'ArrowLeft', 'X',
  'ArrowDown', 'ArrowDown', 'ArrowRight', 'ArrowRight', 'X',
  'ArrowUp', 'ArrowLeft', 'ArrowLeft', 'ArrowDown', 'ArrowDown', 'X',
  'ArrowRight', 'ArrowRight', 'ArrowRight', 'ArrowUp', 'ArrowLeft', 'X',
];

async function main() {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--start-fullscreen', '--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on('pageerror', (e) => say(`PAGE_ERR: ${e.message.slice(0, 100)}`));
  try {
    say(`OPEN ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);
    const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game")').first();
    if (await playBtn.count()) { await playBtn.click({ timeout: 10000 }); state.clicked = true; say('CLICKED PLAY GAME'); }
    await page.waitForTimeout(9000);
    const canvas = page.locator('canvas.ejs_canvas, canvas').first();
    await page.waitForTimeout(1500);
    await page.bringToFront().catch(() => {});
    try {
      await page.locator('.as-game-fullscreen, button[id*=fullscreen]').first().click({ timeout: 5000 });
      state.fullscreen = true; say('FULLSCREEN ON');
      await page.waitForTimeout(1200);
    } catch (e) { say('no fullscreen button'); }

    // ---- BOOT: press X until title screen leaves (gameplay begins)
    let boot = 0;
    while (boot < 14) {
      const t = await ocrCrop(page, canvas, 'boot');
      state.lastOcr = t;
      const m = textMarkers(t);
      say(`boot[${boot}] ocr="${t.slice(0, 60)}" alive=${m.alive} players=${m.players} round2=${m.round2}`);
      if (!m.players) { state.started = true; say('GAME STARTED (title gone)'); break; }
      await page.keyboard.press('X');
      await page.waitForTimeout(1400);
      boot++;
    }
    if (!state.started) say(`boot exhausted (${boot}) — still title`);

    // ---- PLAY LOOP
    let prev = '', idleStreak = 0;
    const idle = [];
    while (state.steps < maxSteps && !state.win && !state.dead) {
      state.steps += 1;
      const key = pattern[state.steps % pattern.length];
      await page.keyboard.down(key);
      await page.waitForTimeout(300);
      await page.keyboard.up(key);
      await page.waitForTimeout(120);

      if (state.steps % 8 === 0) {
        const t = await ocrCrop(page, canvas, 'play');
        state.lastOcr = t;
        const m = textMarkers(t);
        say(`step ${state.steps} key=${key} ocr="${t.slice(0, 70)}" round2=${m.round2} gameOver=${m.gameOver} alive=${m.alive}`);
        if (m.round2) { state.win = true; say('*** LEVEL CLEARED: ROUND 2 DETECTED ***'); break; }
        if (m.gameOver) { state.dead = true; say('GAME OVER'); break; }
        if (t && t === prev) idleStreak++; else idleStreak = 0;
        prev = t;
        idle.push([state.steps, idleStreak]);
        if (idleStreak >= 5) {
          say(`idle at ${state.steps} — restart round`);
          for (const k of ['X']) { await page.keyboard.press(k); await page.waitForTimeout(800); }
          idleStreak = 0;
        }
      }
    }
    say(`DONE steps=${state.steps} win=${state.win} dead=${state.dead}`);
  } catch (e) {
    say(`DRIVER_ERR: ${e.message.slice(0, 250)}`);
    state.error = e.message.slice(0, 400);
  } finally {
    state.running = false;
    state.ts = Date.now();
    fs.writeFileSync(path.join(tmp, 'autopilot_state.json'), JSON.stringify(state));
    await page.waitForTimeout(2500);
    await browser.close();
  }
}

main();