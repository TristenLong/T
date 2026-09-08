import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';

async function main() {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto('https://arcadespot.com/game/dig-dug/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(6000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game"), [id*=play]').first();
  try { if (await playBtn.count()) { await playBtn.click({ timeout: 8000 }); } } catch (e) {}
  await page.waitForTimeout(9000);
  await page.evaluate(() => {
    const E = window.EJS_emulator;
    window.__SIM3 = E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']);
    const gm = E.gameManager;
    window.__GM = gm; window.__FF = (v) => gm.toggleFastForward(v);
  });
  const canvas = page.locator('canvas.ejs_canvas, canvas#nes, canvas').first();
  const box = await canvas.boundingBox();
  const shot = async (name) => {
    const png = `${tmp}/${name}.png`;
    fs.writeFileSync(png, await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } }));
    return png;
  };
  const press = (b, ms) => page.evaluate((x) => { window.__SIM3(0, x, 1); }, b).then(() => page.waitForTimeout(ms)).then(() => page.evaluate((x) => { window.__SIM3(0, x, 0); }, b));
  for (let b2 = 0; b2 < 8; b2++) { await press(3, 400); await press(8, 400); await page.waitForTimeout(1200); }
  await page.waitForTimeout(800);
  await page.evaluate(() => { window.__SAVED = window.__GM.getState(); });

  // helper: sample 2 screenshots 6 wall-clock s apart while pressing no input; diff pixels
  const diffFrames = async (ffOn, tag) => {
    await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
    if (ffOn) await page.evaluate(() => { window.__FF(1); });
    await page.waitForTimeout(1500);
    await shot(`f_${tag}_a`);
    await page.waitForTimeout(6000);
    await shot(`f_${tag}_b`);
    await page.evaluate(() => { window.__FF(0); });
    const out = execFileSync(venvPy, ['C:/Users/trist/gemini-voice-assistant/dd_diff.py', `${tmp}/f_${tag}_a.png`, `${tmp}/f_${tag}_b.png`], { encoding: 'utf8', timeout: 20000 });
    const j = JSON.parse(out.trim());
    return j;
  };

  const normal = await diffFrames(false, 'n');
  console.log('NORMAL diff:', JSON.stringify(normal));
  const ff = await diffFrames(true, 'g');
  console.log('FF diff    :', JSON.stringify(ff));
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });