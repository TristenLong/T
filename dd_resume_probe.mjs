import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';

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
    window.__M = E.Module;
  });
  const canvas = page.locator('canvas.ejs_canvas, canvas#nes, canvas').first();
  const box = await canvas.boundingBox();
  const shot = async (name) => {
    const png = `${tmp}/${name}.png`;
    fs.writeFileSync(png, await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } }));
    return png;
  };
  const press = (b, ms) => page.evaluate((x) => { window.__SIM3(0, x, 1); }, b).then(() => page.waitForTimeout(ms)).then(() => page.evaluate((x) => { window.__SIM3(0, x, 0); }, b));
  const diff = (ta, tb) => JSON.parse(execFileSync(venvPy, ['C:/Users/trist/gemini-voice-assistant/dd_diff.py', ta, tb], { encoding: 'utf8', timeout: 20000 }).trim());

  await press(3, 60);
  await page.waitForTimeout(2500);
  await press(7, 800);
  await page.waitForTimeout(400);
  await page.evaluate(() => { window.__SAVED = window.__GM.getState(); });
  console.log('probe: saved, now advance a bit');
  await press(7, 1200);
  await page.waitForTimeout(300);
  await shot('pre');

  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.waitForTimeout(900);
  // try resume methods
  await page.evaluate(() => {
    const E = window.EJS_emulator;
    try { window.__GM.toggleMainLoop(true); } catch (e) {}
  });
  await page.waitForTimeout(300);
  await shot('r1');
  await press(6, 1000);
  await shot('r2');
  console.log('after loadState+toggleMainLoop(true)+press-left:', JSON.stringify(diff(`${tmp}/r1.png`, `${tmp}/r2.png`).moving));

  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });