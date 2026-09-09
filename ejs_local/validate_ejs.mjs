// Standalone validation of the self-hosted EJS Dig Dug harness: page loads,
// EJS core boots, canvas renders game pixels, OCR sees the title/score text.
// Usage: node validate_ejs.mjs   (server must be running on 8801)
import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';
import { execFileSync } from 'child_process';

const BASE = 'http://127.0.0.1:8801/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';

const browser = await chromium.launch({ headless: true, executablePath: chromePath, args: ['--enable-unsafe-swiftshader', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
const errs = [];
page.on('console', (m) => { if (m.type() === 'error') errs.push('CONSOLE: ' + m.text().slice(0, 160)); });
page.on('pageerror', (e) => errs.push('PAGE_ERR: ' + String(e.message || e).slice(0, 160)));
page.on('requestfailed', (r) => errs.push('REQ_FAIL: ' + r.url().slice(0, 110) + ' ' + (r.failure() ? r.failure().errorText : '')));

console.log('loading', BASE);
await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 60000 });

let ejs = false;
for (let i = 0; i < 60; i++) {
  ejs = await page.evaluate(() => { try { return !!(window.EJS_emulator && document.querySelector('canvas')); } catch (e) { return false; } }).catch(() => false);
  if (ejs) break;
  await page.waitForTimeout(1000);
}
console.log('EJS_emulator + canvas present:', ejs);
if (!ejs) { console.log('ERRORS:'); errs.slice(0, 20).forEach((e) => console.log('  ' + e)); await browser.close(); process.exit(1); }

// give the core time to download/decompress/boot (local files + small ROM)
await page.waitForTimeout(25000);

const prog = await page.evaluate(() => {
  try {
    const el = document.querySelector('.text, #dd');
    return el ? el.textContent.replace(/\s+/g, ' ').slice(0, 120) : '(none)';
  } catch (e) { return '(err)'; }
});
console.log('ui text:', prog);

const box = await page.locator('canvas').first().boundingBox().catch(() => null);
console.log('canvas box:', JSON.stringify(box));
const png = path.join(tmp, 'ejs_home.png');
await page.screenshot({ path: png, clip: box || undefined });

const ink = await page.evaluate(() => {
  try {
    const c = document.querySelector('canvas');
    if (!c) return -1;
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (!gl) return -2;
    const w = c.width, h = c.height;
    const buf = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
    let lit = 0;
    for (let i = 0; i < buf.length; i += 16) { if (buf[i] > 40 || buf[i + 1] > 40 || buf[i + 2] > 40) lit++; }
    return Math.round((lit / (buf.length / 16)) * 1000) / 10;
  } catch (e) { return -3; }
});
console.log('canvas ink %:', ink, '(>0 means the game is drawing)');

let ocr = '';
try {
  const env = { ...process.env, PATH: 'C:/Program Files/Tesseract-OCR;' + (process.env.PATH || '') };
  const out = execFileSync(venvPy, [ocrPy, png], { env, encoding: 'utf8', timeout: 25000 });
  const m = out.match(/TEXT=([^\n]*)/);
  ocr = m ? m[1].trim() : '(none)';
} catch (e) { ocr = 'OCR_ERR'; }
console.log('OCR:', ocr.slice(0, 140));

// does the agent's public API surface exist here too?
const api = await page.evaluate(() => {
  try {
    const E = window.EJS_emulator, gm = E && E.gameManager;
    return {
      gameManager: !!gm,
      simulateInput: !!E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']),
      getState: !!(gm && typeof gm.getState === 'function'),
      loadState: !!(gm && typeof gm.loadState === 'function'),
      slowMotion: !!(gm && typeof gm.toggleSlowMotion === 'function'),
      mainLoop: !!(gm && typeof gm.toggleMainLoop === 'function'),
    };
  } catch (e) { return null; }
});
console.log('API surface:', JSON.stringify(api));

console.log('ERRORS:');
errs.slice(0, 25).forEach((e) => console.log('  ' + e));
await browser.close();