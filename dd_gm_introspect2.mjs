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
    const gm = E.gameManager;
    const collect = {};
    for (const k of ['toggleMainLoop', 'getFrameNum', 'clearEJSResetTimer', 'restart', 'quickSave', 'quickLoad', 'setFastForwardRatio', 'simulateInput']) {
      try { if (typeof gm[k] === 'function') collect[k] = gm[k].toString().slice(0, 700); } catch (e) { collect[k] = 'ERR ' + e.message; }
    }
    collect.storage = typeof globalThis.localStorage === 'object' ? Object.keys(globalThis.localStorage).filter(k => /sav/i.test(k)).slice(0, 20) : null;
    const E2 = window.EJS_emulator;
    collect.moduleExports = Object.keys(E2.Module).filter((k) => /cmd_|load|save|main_loop|uncompress_state/i.test(k)).slice(0, 80);
    return collect;
  });
  console.log('--- toggleMainLoop ---'); console.log(out.toggleMainLoop);
  console.log('--- functions.loadState (from newline) ---');
  console.log(await page.evaluate(() => {
    try { const f = window.EJS_emulator.gameManager.functions; return Object.getOwnPropertyNames(f).map(k => k + '=' + (typeof f[k] === 'function' ? 'fn' : typeof f[k])).join('\n'); } catch (e) { return 'ERR' + e.message; }
  }));
  console.log('--- quickSave ---'); console.log(out.quickSave);
  console.log('--- quickLoad ---'); console.log(out.quickLoad);
  console.log('--- moduleExports ---'); console.log(out.moduleExports.join(', '));
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });