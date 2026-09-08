import { chromium } from 'playwright';
import fs from 'fs';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';

const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--start-fullscreen', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game")').first();
  if (await playBtn.count()) { await playBtn.click({ timeout: 10000 }); console.log('CLICKED PLAY'); }
  await page.waitForTimeout(9000);
  const canvas = page.locator('canvas.ejs_canvas, canvas').first();
  await page.evaluate(() => { window.__SIM3 = window.EJS_emulator.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']); });
  const press = async (b, holdMs) => {
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 1); } catch (e) {} }, b);
    await page.waitForTimeout(holdMs);
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 0); } catch (e) {} }, b);
    await page.waitForTimeout(400);
  };
  // wait until title appears
  await page.waitForTimeout(2000);
  // start game
  await press(3, 400);
  await page.waitForTimeout(1500);
  // dig slowly to change state from the spawn position so OCR/cluster check works
  for (let i = 0; i < 4; i++) { await press(6, 600); } // left 4
  await page.waitForTimeout(1000);
  const box = await canvas.boundingBox();
  console.log('CANVAS BOX:', JSON.stringify(box));
  for (let i = 0; i < 3; i++) {
    const shot = await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } });
    const f = `${tmp}/dd_play${i}.png`;
    fs.writeFileSync(f, shot);
    console.log('SAVED', f, shot.length);
    await page.waitForTimeout(2000);
  }
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}