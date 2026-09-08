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
    window.__FF = (v) => { try { E.gameManager.toggleFastForward(v); } catch (e) {} };
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
  const diff = (ta, tb) => JSON.parse(execFileSync(venvPy, ['C:/Users/trist/gemini-voice-assistant/dd_diff.py', ta, tb], { encoding: 'utf8', timeout: 20000 }).trim());

  // read before pressing start
  let p = await shot('s0'); console.log('before start :', ocr(p).slice(0, 40));
  await press(3, 60); // START tap
  await page.waitForTimeout(1500);
  p = await shot('s1'); console.log('after  start :', ocr(p).slice(0, 40));
  await page.waitForTimeout(5000);
  p = await shot('s2'); console.log('after  start+5s:', ocr(p).slice(0, 40));
  // motion between s1 and s2 (live game: enemies move)
  console.log('live-motion   :', JSON.stringify(diff(`${tmp}/s1.png`, `${tmp}/s2.png`).moving));

  // hold RIGHT 2s, then diff again
  await press(7, 2000);
  await page.waitForTimeout(300);
  p = await shot('s3');
  console.log('after  right :', ocr(p).slice(0, 40));
  console.log('right-motion  :', JSON.stringify(diff(`${tmp}/s1.png`, `${tmp}/s3.png`).moving));

  // FF on, hold RIGHT 2s, diff (does FF accelerate?)
  await page.evaluate(() => { window.__FF(1); });
  await page.waitForTimeout(400);
  await press(7, 2000);
  await page.waitForTimeout(300);
  await page.evaluate(() => { window.__FF(0); });
  p = await shot('s4');
  console.log('ff+right      :', ocr(p).slice(0, 40));
  console.log('ff-right mv   :', JSON.stringify(diff(`${tmp}/s1.png`, `${tmp}/s4.png`).moving));
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });