import { chromium } from 'playwright';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';

async function main() {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on('pageerror', (e) => console.log('PAGE_ERR', e.message.slice(0, 150)));
  await page.goto('https://arcadespot.com/game/dig-dug/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(6000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game"), [id*=play]').first();
  try { if (await playBtn.count()) { await playBtn.click({ timeout: 8000 }); } } catch (e) {}
  await page.waitForTimeout(10000);
  const out = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const f = E.gameManager.functions;
    // try to get function source from the module
    const M = E.Module;
    const res = {};
    // look at minified functions via toString on the wrapped function objects
    for (const k of ['loadState', 'toggleMainLoop', 'saveStateInfo', 'simulateInput', 'getFrameNum']) {
      try { res[k] = f[k].toString().slice(0, 500); } catch (e) { res[k] = 'ERR'; }
    }
    // Read the raw JS for the emulator? find the gameManager function source in loaded scripts via performance entries
    res.scripts = performance.getEntriesByType('resource').filter(r => /\.js/.test(r.name)).map(r => r.name).slice(-15);
    return res;
  });
  console.log('--- functions sources ---');
  console.log(JSON.stringify(out.functionsToStr, null, 2));
  for (const [k, v] of Object.entries(out)) {
    if (k === 'functionsToStr') continue;
    console.log(`--- ${k} ---`);
    console.log(JSON.stringify(v).slice(0, 1200));
  }
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });