import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';
const tesseractPath = 'C:/Program Files/Tesseract-OCR';

async function cropOcr(page, canvas, name) {
  const box = await canvas.boundingBox();
  if (!box) return '';
  fs.writeFileSync(`${tmp}/${name}.png`, await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } }));
  try {
    const env = { ...process.env, PATH: `${tesseractPath};${process.env.PATH || ''}` };
    const out = execFileSync(venvPy, [ocrPy, `${tmp}/${name}.png`], { env, encoding: 'utf8', timeout: 25000 });
    const m = out.match(/TEXT=([^\n]*)/);
    return m ? m[1].trim() : '';
  } catch (e) { return ''; }
}

const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--start-fullscreen', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
page.on('pageerror', (e) => console.log('PAGE_ERR:', String(e).slice(0, 160)));
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game")').first();
  if (await playBtn.count()) { await playBtn.click({ timeout: 10000 }); console.log('CLICKED PLAY'); }
  await page.waitForTimeout(9000);
  const canvas = page.locator('canvas.ejs_canvas, canvas').first();

  // Deep scan the whole window for an object carrying a LIVE Module (anything with .Module.cwrap)
  // AND a simulateInput-capable functions bag we can repoint.
  const scan = await page.evaluate(() => {
    const out = { emulatorModule: false, gmModule: false, qv: {}, emulatorStarted: false };
    try {
      const E = window.EJS_emulator;
      out.emulatorStarted = !!E.started;
      out.emulatorModule = !!(E && E.Module && E.Module.cwrap);
      if (E && E.Module && E.Module.cwrap) {
        out.qv.version = (E.ejs_version || '');
        try { out.qv.cmd = E.Module.cwrap ? typeof E.Module.cwrap('cmd_take_screenshot') : 'none'; } catch (e) {}
        try { out.qv.hasSim = typeof E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']) === 'function'; } catch (e) {}
      }
    } catch (e) { out.err1 = e.message; }
    try {
      const gm = window.EJS_GameManager;
      out.gmModule = !!(gm && gm.Module && gm.Module.cwrap);
      if (gm && gm.Module && gm.Module.cwrap) {
        try { out.qv.gm_fns = Object.keys(gm.functions || {}); } catch (e) {}
      }
    } catch (e) { out.err2 = e.message; }
    return out;
  });
  console.log('SCAN:', JSON.stringify(scan));

  // Route A: emulate the class constructor path by binding the prototype method with live Module.
  const bound = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const GM = window.EJS_GameManager;
    if (!E || !GM || !E.Module || !E.Module.cwrap) return { ok: false, why: 'no live module on E' };
    const sim = GM.prototype.simulateInput;
    if (typeof sim !== 'function') return { ok: false, why: 'no proto sim' };
    // The method uses `this.Module`/`this.EJS` in its body via the class fields; bind a proxy
    // object that carries the live Module + FS + functions bag.
    const bag = {
      functions: {
        simulateInput: E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']),
        toggleMainLoop: E.Module.cwrap('toggleMainLoop', 'null', ['number']),
      },
      Module: E.Module,
      EJS: E,
      FS: E.Module.FS,
    };
    try {
      const tick = bag.functions.toggleMainLoop(1);
      window.__SIM = bag.functions.simulateInput;
      return { ok: true, simWrapped: typeof window.__SIM };
    } catch (e) {
      return { ok: false, why: e.message };
    }
  });
  console.log('BOUND:', JSON.stringify(bound));

  // Route B: use the prototype simulateInput bound to a shim instance carrying the live Module.
  const protoSim = await page.evaluate(() => {
    try {
      const E = window.EJS_emulator;
      const GM = window.EJS_GameManager;
      const sim = GM.prototype.simulateInput;
      const shim = Object.create(GM.prototype);
      Object.defineProperties(shim, {
        Module: { value: E.Module, writable: false },
        EJS: { value: E, writable: false },
        FS: { value: E.Module.FS, writable: false },
        functions: { value: { simulateInput: E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']) }, writable: false },
      });
      window.__SIM2 = sim.bind(shim);
      return { ok: typeof window.__SIM2 === 'function' };
    } catch (e) { return { ok: false, why: e.message }; }
  });
  console.log('PROTO_SIM:', JSON.stringify(protoSim));

  // Try pressing simulate via whichever worked. Standard NES core joypad: B=0,Y=1,Select=2,Start=3,Up=4,Down=5,Left=6,Right=7,A=8,X=9
  const tryPressed = async (btn, holdMs) => {
    await page.evaluate((b) => {
      const f = window.__SIM || window.__SIM2;
      if (f) { try { f(b, 1); } catch (e) {} }
    }, btn);
    await page.waitForTimeout(holdMs);
    await page.evaluate((b) => {
      const f = window.__SIM || window.__SIM2;
      if (f) { try { f(b, 0); } catch (e) {} }
    }, btn);
    await page.waitForTimeout(600);
  };

  // Insert coin attempt + Start on the title screen.
  for (const b of [3, 3, 3, 3]) await tryPressed(b, 400); // START x4
  console.log('AFTER START:', (await cropOcr(page, canvas, 'r_start')).slice(0, 80));

  for (const b of [8, 9]) { await tryPressed(b, 300); } // A & B
  console.log('AFTER AB:', (await cropOcr(page, canvas, 'r_ab')).slice(0, 80));

  // Move the d-pad around; check canvas change via OCR bright count path
  for (const b of [6, 6, 5, 5, 7, 7, 4, 4]) await tryPressed(b, 350);
  console.log('AFTER MOVE:', (await cropOcr(page, canvas, 'r_move')).slice(0, 80));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 400));
} finally {
  await browser.close();
}