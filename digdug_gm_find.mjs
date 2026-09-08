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

  // Find the LIVE instance: scan window globals for anything with .functions.simulateInput
  const finder = await page.evaluate(() => {
    const out = { candidates: [] };
    const scan = (v, path, depth) => {
      if (depth > 3) return;
      if (!v || (typeof v !== 'object' && typeof v !== 'function')) return;
      try {
        if (v.functions && typeof v.functions.simulateInput === 'function') {
          out.candidates.push({ path, hasModule: !!(v.Module && v.Module.cwrap), keys: Object.keys(v.functions) });
        }
      } catch (e) {}
      try {
        for (const k of Object.keys(v)) {
          if (k.startsWith('EJS_') || k === 'GameManager' || k === 'Module' || k === 'emulator' || k === 'EJS') {
            scan(v[k], `${path}.${k}`, depth + 1);
          }
        }
      } catch (e) {}
    };
    scan(window, 'window', 0);
    return out;
  });
  console.log('FINDER:', JSON.stringify(finder));

  // Try via the loader's internal reference: EJS holds instance in its config closure,
  // but EmulatorJS also exposes EJS_GameManager as instance in loader builds. Try direct:
  const direct = await page.evaluate(() => {
    const out = {
      type: typeof window.EJS_GameManager,
      proto: null,
      fnKeys: null,
      instanceHas: false,
      emulatorGM: null,
    };
    try {
      const gm = window.EJS_GameManager;
      out.proto = gm.prototype ? Object.getOwnPropertyNames(gm.prototype) : null;
    } catch (e) {}
    try {
      const gm = window.EJS_GameManager;
      out.instanceHas = !!(gm && gm.functions && typeof gm.functions.simulateInput === 'function');
      if (gm && gm.functions) out.fnKeys = Object.keys(gm.functions);
    } catch (e) {}
    try {
      out.emulatorGM = window.EJS_emulator && window.EJS_emulator.GameManager ? 'present' : 'missing';
    } catch (e) {}
    return out;
  });
  console.log('DIRECT:', JSON.stringify(direct));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 400));
} finally {
  await browser.close();
}