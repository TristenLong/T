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
    // native export handles
    const M = E.Module;
    window.__CMD_SAVE = M['_cmd_save_state'];
    window.__LOAD_STATE = M['_load_state'];
    window.__FS = M['FS'];
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

  await press(3, 60);
  await page.waitForTimeout(2000);
  await press(7, 1200); // move right a little to be in-game
  await page.waitForTimeout(500);
  console.log('MM: fs check ->', await page.evaluate(() => { try { const r = window.__FS.readdir('/'); return JSON.stringify(r).slice(0, 120); } catch (e) { return 'ERR ' + e.message; } }));

  // --- A. gm getState + gm loadState round-trip; does motion resume?
  await page.evaluate(() => { window.__SAVED = window.__GM.getState(); });
  // advance some so a rewind is observable
  await press(7, 1000); await press(6, 1000);
  await shot('preA');
  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.waitForTimeout(1200);
  await shot('postA_m');
  console.log('A. gm.loadState motion:', JSON.stringify(diff(`${tmp}/postA_m.png`, `${tmp}/preA.png`).moving));
  // is it still alive? press left and measure motion after load
  await shot('A_before');
  await press(6, 1000);
  await shot('A_after');
  console.log('A. after-gmLoad press-left motion:', JSON.stringify(diff(`${tmp}/A_before.png`, `${tmp}/A_after.png`).moving));

  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });