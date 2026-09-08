import { chromium } from 'playwright';
import fs from 'fs';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';

const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--start-fullscreen', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const shot = async (name) => {
  const canvas = page.locator('canvas.ejs_canvas, canvas').first();
  const box = await canvas.boundingBox();
  const s = await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } });
  fs.writeFileSync(`${tmp}/${name}.png`, s);
};
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game")').first();
  if (await playBtn.count()) { await playBtn.click({ timeout: 10000 }); console.log('CLICKED PLAY'); }
  await page.waitForTimeout(9000);
  await page.evaluate(() => {
    const E = window.EJS_emulator;
    window.__GM = E.gameManager;
    window.__SIM3 = E.gameManager.Module.cwrap('_simulate_input', 'null', ['number', 'number', 'number']);
  });
  const press = async (b, holdMs) => {
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 1); } catch (e) {} }, b);
    await page.waitForTimeout(holdMs);
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 0); } catch (e) {} }, b);
    await page.waitForTimeout(300);
  };
  // enter gameplay
  let entered = false;
  for (let i = 0; i < 8; i++) { await press(3, 400); await page.waitForTimeout(800); }
  await page.waitForTimeout(1500);
  // definitely in gameplay; dig up briefly to make a tunnel
  await press(4, 500); // up
  await shot('dd_rt_saveframe');

  // SAVE state bytes
  const saved = await page.evaluate(() => { window.__ST = window.__GM.getState(); return window.__ST.byteLength; });
  console.log('state bytes:', saved);
  // deviate: move down and right a lot
  for (let i = 0; i < 3; i++) await press(5, 800); // down
  for (let i = 0; i < 3; i++) await press(7, 800); // right
  await shot('dd_rt_moved');
  console.log('deviated');

  // restore
  await page.evaluate(() => { window.__GM.loadState(window.__ST); });
  // let it settle (Asyncify restores over a few frames)
  await page.waitForTimeout(2500);
  await shot('dd_rt_restored');
  console.log('restored');
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}