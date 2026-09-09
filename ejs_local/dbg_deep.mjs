// Deeper harness debug: why is the game screen black?
import { chromium } from 'playwright';
const BASE = 'http://127.0.0.1:8801/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const browser = await chromium.launch({ headless: true, executablePath: chromePath, args: ['--enable-unsafe-swiftshader', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
page.on('response', (r) => { if (r.status() >= 400 || /sim|start|netplay/.test(r.url())) console.log('HTTP', r.status(), r.url()); });
page.on('console', (m) => { const t = m.text(); if (/error/i.test(m.type()) || /start|emulat|core|game|error/i.test(t)) console.log('CONSOLE[' + m.type() + ']', t.slice(0, 300)); });
page.on('pageerror', (e) => console.log('PAGE_ERR', (e.stack || String(e)).slice(0, 500)));
await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(22000);

const state = await page.evaluate(() => {
  const E = window.EJS_emulator;
  const gm = E && E.gameManager;
  const c = document.querySelector('canvas');
  let ink = -1;
  try {
    if (c) { const gl = c.getContext('webgl2') || c.getContext('webgl'); if (gl) { const w = c.width, h = c.height; const b = new Uint8Array(w * h * 4); gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, b); let lit = 0; for (let i = 0; i < b.length; i += 16) if (b[i] > 40 || b[i + 1] > 40 || b[i + 2] > 40) lit++; ink = Math.round((lit / (b.length / 16)) * 1000) / 10; } }
  } catch (e) { ink = -3; }
  const buttons = Array.from(document.querySelectorAll('button')).map((b) => b.textContent.trim()).slice(0, 12);
  const overlays = Array.from(document.querySelectorAll('div')).map((d) => d.textContent.trim()).filter((t) => t && t.length < 80).slice(-15);
  return {
    hasCanvas: !!c, canvasSize: c ? c.width + 'x' + c.height : null,
    ink,
    mainLoopOk: !!(gm && gm.mainLoopRunning),
    isPlaying: !!(gm && (gm.mainLoopRunning === true || gm.mainLoopRunning === undefined && window.__EJSSTART !== undefined)),
    ejsStartFlag: window.__EJSSTART === 1,
    buttons, overlays,
  };
});
console.log(JSON.stringify(state, null, 2));

// try one simulated input + snapshot again
await page.evaluate(() => { try { window.__SIM3(0, 7, 1); } catch (e) {} });
await page.waitForTimeout(1200);
await page.evaluate(() => { try { window.__SIM3(0, 7, 0); } catch (e) {} });
const ink2 = await page.evaluate(() => { try { const c = document.querySelector('canvas'); const gl = c.getContext('webgl2') || c.getContext('webgl'); const w = c.width, h = c.height; const b = new Uint8Array(w * h * 4); gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, b); let lit = 0; for (let i = 0; i < b.length; i += 16) if (b[i] > 40 || b[i+1] > 40 || b[i+2] > 40) lit++; return lit / (b.length / 16); } catch (e) { return -1; } });
console.log('ink after input:', ink2);

// trusted user gesture (this is what unlocks EJS): click the EJS "Start Game"
// button exactly like the agent clicks the arcadespot Play CTA.
let clicked = false;
const startBtn = page.locator('.gamestarted .start-button, button.start-button, .ejs_start_button, button:has-text("Start Game")').first();
if (await startBtn.count()) { clicked = true; await startBtn.click({ timeout: 8000 }); console.log('clicked EJS Start Game button'); }
if (!clicked) { const anyBtn = page.locator('button:has-text("Start")').first(); if (await anyBtn.count()) { await anyBtn.click({ timeout: 8000 }); console.log('clicked generic Start button'); clicked = true; } }
if (!clicked) console.log('NO start button found');
// poll until the emulator is actually drawing (core decompress + SwiftShader boot)
let ink = -1, mainLoop = false;
for (let i = 0; i < 20; i++) {
  await page.waitForTimeout(3000);
  const s = await page.evaluate(() => {
    const gm = window.EJS_emulator && window.EJS_emulator.gameManager;
    const c = document.querySelector('canvas');
    let k = -1;
    try { if (c) { const gl = c.getContext('webgl2') || c.getContext('webgl'); if (gl) { const w = c.width, h = c.height; const b = new Uint8Array(w * h * 4); gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, b); let lit = 0; for (let j = 0; j < b.length; j += 16) if (b[j] > 40 || b[j + 1] > 40 || b[j + 2] > 40) lit++; k = Math.round((lit / (b.length / 16)) * 1000) / 10; } } } catch (e) { k = -3; }
    return { k, ml: !!(gm && gm.mainLoopRunning) };
  });
  ink = s.k; mainLoop = s.ml;
  console.log(`t+${(i + 1) * 3}s ink=${ink} mainLoop=${mainLoop}`);
  if (ink > 0) break;
}
console.log('final ink:', ink, 'mainLoop:', mainLoop);

if (ink > 0) {
  const png = 'C:/Users/trist/AppData/Local/Temp/opencode/ejs_home3.png';
  await page.screenshot({ path: png });
  const { execFileSync } = await import('child_process');
  try {
    const env = { ...process.env, PATH: 'C:/Program Files/Tesseract-OCR;' + (process.env.PATH || '') };
    const out = execFileSync('C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe', ['C:/Users/trist/gemini-voice-assistant/ocr_crop.py', png], { env, encoding: 'utf8', timeout: 25000 });
    const m = out.match(/TEXT=([^\n]*)/);
    console.log('OCR:', m ? m[1].trim() : '(none)');
  } catch (e) { console.log('OCR err:', e.message.split('\n')[0]); }
}
await browser.close();