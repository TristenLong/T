import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';

async function main() {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto('https://arcadespot.com/game/dig-dug/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(6000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game"), [id*=play]').first();
  try { if (await playBtn.count()) { await playBtn.click({ timeout: 8000 }); } } catch (e) {}
  await page.waitForTimeout(9000);
  const sim = await page.evaluate(() => {
    try {
      const E = window.EJS_emulator;
      if (E && E.Module && E.Module.cwrap) {
        window.__SIM3 = E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']);
        const gm = E.gameManager;
        if (gm) { window.__GM = gm; window.__FF = (v) => gm.toggleFastForward(v); }
        return true;
      }
    } catch (e) {}
    return false;
  });
  const canvas = page.locator('canvas.ejs_canvas, canvas#nes, canvas').first();
  const box = await canvas.boundingBox();

  const shot = async (name) => {
    const png = `${tmp}/${name}.png`;
    fs.writeFileSync(png, await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } }));
    return png;
  };
  const ocr = (png) => {
    try { const o = execFileSync(venvPy, [ocrPy, png], { env: { ...process.env, PATH: 'C:/Program Files/Tesseract-OCR;' + (process.env.PATH || '') }, encoding: 'utf8', timeout: 25000 }); const m = o.match(/TEXT=([^\n]*)/); return m ? m[1].trim() : ''; } catch (e) { return ''; }
  };
  const press = (b, ms) => page.evaluate((x) => { window.__SIM3(0, x, 1); }, b).then(() => page.waitForTimeout(ms)).then(() => page.evaluate((x) => { window.__SIM3(0, x, 0); }, b));

  console.log('sim bound:', sim);
  // boot into a game
  for (let b2 = 0; b2 < 8; b2++) { await press(3, 400); await press(8, 400); await page.waitForTimeout(1200); }
  await page.waitForTimeout(1000);
  // save state
  await page.evaluate(() => { window.__SAVED = window.__GM.getState(); });
  console.log('saved state bytes:', await page.evaluate(() => window.__SAVED.length));

  // normal-speed window: play for 8 wall-clock seconds, measure emulated progress via score OCR
  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.waitForTimeout(1200);
  let png = await shot('ff_a');
  console.log('normal.before:', ocr(png).slice(0, 40));
  await page.waitForTimeout(8000);
  png = await shot('ff_b');
  console.log('normal.after :', ocr(png).slice(0, 40));

  // fast-forward window: same save, but FF on
  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.evaluate(() => { window.__FF(1); });
  await page.waitForTimeout(1200);
  png = await shot('ff_c');
  console.log('ff.before    :', ocr(png).slice(0, 40));
  await page.waitForTimeout(8000);
  png = await shot('ff_d');
  console.log('ff.after     :', ocr(png).slice(0, 40));
  await page.evaluate(() => { window.__FF(0); });
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });