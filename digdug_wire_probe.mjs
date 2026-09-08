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

  // Inspect how EJS itself passes input -> will reveal signature + button enums.
  const wiring = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const out = { control0: null, haveSimSrc: false, gmProtoSimSrc: '', checkGP: '', setCtrlSrc: '' };
    try {
      const c = E.controls && E.controls[0];
      out.control0 = c ? Object.keys(c) : 'none';
      if (c && c.handleInput) out.setCtrlSrc = c.handleInput.toString().slice(0, 600);
    } catch (e) { out.err1 = e.message; }
    try {
      const GM = window.EJS_GameManager;
      out.gmProtoSimSrc = GM.prototype.simulateInput.toString().slice(0, 800);
    } catch (e) {}
    try {
      out.checkGP = E.checkGamepadInputs.toString().slice(0, 500);
    } catch (e) {}
    try {
      // find any EJS method that calls simulate_input with numbers
      const GM = window.EJS_GameManager;
      const src = GM.prototype.simulateInput.toString();
      out.haveSimSrc = src.includes('simulate_input');
    } catch (e) {}
    return out;
  });
  console.log('WIRE:', JSON.stringify(wiring, null, 1).slice(0, 3500));

  // Route: try the 3-arg likely signature (port, button, value) with port 0.
  await page.evaluate(() => {
    const E = window.EJS_emulator;
    window.__SIM3 = E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']);
  });
  const sim = async (port, btn, val, holdMs) => {
    await page.evaluate(([p, b, v]) => { try { window.__SIM3(p, b, v); } catch (e) {} }, [port, btn, val]);
    await page.waitForTimeout(holdMs);
    await page.evaluate(([p, b]) => { try { window.__SIM3(p, b, 0); } catch (e) {} }, [port, btn]);
    await page.waitForTimeout(500);
  };
  // Try RetroArch NES joypad ids on port 0: START=3, UP=4, DOWN=5, LEFT=6, RIGHT=7, A=8, B=0
  const before = await cropOcr(page, canvas, 'w_before');
  console.log('BEFORE:', before.slice(0, 70));
  for (let i = 0; i < 5; i++) await sim(0, 3, 1, 350);
  console.log('AFTER START(0,3):', (await cropOcr(page, canvas, 'w_start')).slice(0, 70));
  for (let i = 0; i < 3; i++) { await sim(0, 8, 1, 250); await sim(0, 0, 1, 250); }
  console.log('AFTER A/B:', (await cropOcr(page, canvas, 'w_ab')).slice(0, 70));
  await sim(0, 3, 1, 400);
  console.log('AFTER START again:', (await cropOcr(page, canvas, 'w_start2')).slice(0, 70));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 400));
} finally {
  await browser.close();
}