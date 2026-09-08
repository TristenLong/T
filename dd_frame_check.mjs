import { chromium } from 'playwright';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';

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
  const press = (b, ms) => page.evaluate((x) => { window.__SIM3(0, x, 1); }, b).then(() => page.waitForTimeout(ms)).then(() => page.evaluate((x) => { window.__SIM3(0, x, 0); }, b));
  const frame = () => page.evaluate(() => { try { return window.__GM.getFrameNum(); } catch (e) { return 'ERR:' + e.message; } });

  // measure frame throughput live
  console.log('live t0 frame=', await frame());
  await page.waitForTimeout(2000);
  console.log('live t1 frame=', await frame(), '(+2s)');
  console.log('low = main loop throttled/stopped when window unfocused?');

  await press(3, 60);
  await page.waitForTimeout(2500);
  await press(7, 800);
  await page.waitForTimeout(300);
  await page.evaluate(() => { window.__SAVED = window.__GM.getState(); });
  await press(7, 1000);
  console.log('pre-save-advance done');

  console.log('t2 (post move) frame=', await frame());
  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.waitForTimeout(800);
  console.log('t3 (after loadState) frame=', await frame());
  await page.waitForTimeout(2000);
  console.log('t4 (+2s) frame=', await frame());
  await press(6, 800);
  await page.waitForTimeout(200);
  console.log('t5 (after press-left) frame=', await frame());
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });