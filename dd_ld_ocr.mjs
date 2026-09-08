import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';

async function main() {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--start-fullscreen', '--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on('pageerror', (e) => console.log('PAGE_ERR', e.message.slice(0, 150)));
  await page.goto('https://arcadespot.com/game/dig-dug/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(6000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game"), [id*=play]').first();
  try { if (await playBtn.count()) { await playBtn.click({ timeout: 8000 }); } } catch (e) {}
  await page.waitForTimeout(10000);
  await page.bringToFront();
  await page.evaluate(() => {
    const E = window.EJS_emulator;
    window.__SIM3 = E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']);
    window.__GM = E.gameManager;
  });
  const canvas = page.locator('canvas.ejs_canvas, canvas#nes, canvas').first();
  const box = await canvas.boundingBox();
  const shot = async (name) => {
    const png = `${tmp}/${name}.png`;
    fs.writeFileSync(png, await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } }));
    return png;
  };
  const ocr = (png) => { try { const o = execFileSync(venvPy, [ocrPy, png], { env: { ...process.env, PATH: 'C:/Program Files/Tesseract-OCR;' + (process.env.PATH || '') }, encoding: 'utf8', timeout: 25000 }); const m = o.match(/TEXT=([^\n]*)/); return m ? m[1].trim() : ''; } catch (e) { return ''; } };
  const press = (b, ms) => page.evaluate((x) => { window.__SIM3(0, x, 1); }, b).then(() => page.waitForTimeout(ms)).then(() => page.evaluate((x) => { window.__SIM3(0, x, 0); }, b));
  const rgb = (png) => JSON.parse(execFileSync(venvPy, ['C:/Users/trist/gemini-voice-assistant/dd_hist.py', png], { encoding: 'utf8', timeout: 20000 }).trim()).top;

  await press(3, 60);
  await page.waitForTimeout(2500);
  await press(7, 400);
  await page.waitForTimeout(300);
  await shot('live_x');
  console.log('LIVE gameplay   :', ocr(`${tmp}/live_x.png`).slice(0, 45));

  await page.evaluate(() => { window.__SAVED = window.__GM.getState(); });
  console.log('state bytes =', await page.evaluate(() => window.__SAVED.length));
  // wait without touching anything, screen changes live?
  await shot('live_A');
  await page.waitForTimeout(3000);
  await shot('live_B');
  console.log('live_A          :', ocr(`${tmp}/live_A.png`).slice(0, 45));
  console.log('live_B (+3s)    :', ocr(`${tmp}/live_B.png`).slice(0, 45));

  // now loadState and observe
  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.waitForTimeout(1500);
  await shot('ld_A');
  console.log('ld_A (after L)  :', ocr(`${tmp}/ld_A.png`).slice(0, 45));
  await page.waitForTimeout(3000);
  await shot('ld_B');
  console.log('ld_B (+3s)      :', ocr(`${tmp}/ld_B.png`).slice(0, 45));
  // press LEFT 2s
  await press(6, 2000);
  await page.waitForTimeout(300);
  await shot('ld_C');
  console.log('ld_C (left 2s)  :', ocr(`${tmp}/ld_C.png`).slice(0, 45));
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });