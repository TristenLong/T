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
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game")').first();
  if (await playBtn.count()) { await playBtn.click({ timeout: 10000 }); console.log('CLICKED PLAY'); }
  await page.waitForTimeout(9000);
  const canvas = page.locator('canvas.ejs_canvas, canvas').first();
  await canvas.click({ position: { x: 480, y: 240 } }).catch(() => {});

  const before = await cropOcr(page, canvas, 's_before');
  console.log('BEFORE:', before.slice(0, 80));

  // Does simulateInput exist and is the emulator truly running?
  const api = await page.evaluate(() => {
    const gm = window.EJS_GameManager;
    return {
      hasSim: !!(gm && gm.functions && gm.functions.simulateInput),
      started: window.EJS_emulator && window.EJS_emulator.started,
      paused: window.EJS_emulator && window.EJS_emulator.paused,
      ready: window.EJS_emulator && window.EJS_emulator.ready,
    };
  });
  console.log('API:', JSON.stringify(api));

  // The NES joypad order in RetroArch-emulated cores is B,Y,Select,Start,Up,Down,Left,Right,A,X
  // BUT EJS may use its own ids. Sweep 0..16, COIN/START via hold, and OCR after each.
  for (let btn = 0; btn <= 16; btn++) {
    await page.evaluate((b) => {
      const gm = window.EJS_GameManager;
      if (gm && gm.functions && gm.functions.simulateInput) {
        gm.functions.simulateInput(b, 1);
      }
    }, btn);
    await page.waitForTimeout(450);
    await page.evaluate((b) => {
      const gm = window.EJS_GameManager;
      if (gm && gm.functions && gm.functions.simulateInput) {
        gm.functions.simulateInput(b, 0);
      }
    }, btn);
    await page.waitForTimeout(700);
    const t = await cropOcr(page, canvas, 's_press');
    // print only on change from before
    if (t.slice(0, 30) !== before.slice(0, 30)) {
      console.log(`BTN ${btn}: "${t.slice(0, 90)}"`);
    }
  }

  await page.waitForTimeout(1200);
  const after = await cropOcr(page, canvas, 's_after');
  console.log('AFTER:', after.slice(0, 90));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}