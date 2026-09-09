// Headed validation of the local harness (matches the agent's real runtime).
import { chromium } from 'playwright';
import { execFileSync } from 'child_process';

const BASE = 'http://127.0.0.1:8801/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';

const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 1120, height: 740 } });
page.on('pageerror', (e) => console.log('PAGE_ERR', String(e).slice(0, 160)));

await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 60000 });

const startBtn = page.locator('button:has-text("Start Game"), .start-button, .ejs_start_button').first();
for (let i = 0; i < 30; i++) {
  if (await startBtn.count()) { await startBtn.click({ timeout: 8000 }); console.log('clicked EJS Start Game button'); break; }
  await page.waitForTimeout(1000);
}

let ink = -1;
for (let i = 0; i < 30; i++) {
  await page.waitForTimeout(1500);
  ink = await page.evaluate(() => {
    try { const c = document.querySelector('canvas'); if (!c) return -1; const gl = c.getContext('webgl2') || c.getContext('webgl'); if (!gl) return -2; const w = c.width, h = c.height; const b = new Uint8Array(w * h * 4); gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, b); let lit = 0; for (let j = 0; j < b.length; j += 16) if (b[j] > 40 || b[j + 1] > 40 || b[j + 2] > 40) lit++; return Math.round((lit / (b.length / 16)) * 1000) / 10; } catch (e) { return -3; }
  }).catch(() => -99);
  console.log(`t+${(i + 1) * 1.5}s ink=${ink}`);
  if (ink > 0.5) break;
}

const png = 'C:/Users/trist/AppData/Local/Temp/opencode/ejs_headed.png';
await page.screenshot({ path: png });
let ocr = '(no ocr)';
try {
  const env = { ...process.env, PATH: 'C:/Program Files/Tesseract-OCR;' + (process.env.PATH || '') };
  const out = execFileSync('C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe', ['C:/Users/trist/gemini-voice-assistant/ocr_crop.py', png], { env, encoding: 'utf8', timeout: 25000 });
  const m = out.match(/TEXT=([^\n]*)/);
  ocr = m ? m[1].trim() : '(none)';
} catch (e) { ocr = 'OCR_ERR'; }
console.log('final ink:', ink);
console.log('OCR:', ocr.slice(0, 160));
await browser.close();