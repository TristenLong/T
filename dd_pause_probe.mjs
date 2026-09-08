import { chromium } from 'playwright';

const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';

async function main() {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on('pageerror', (e) => console.log('PAGE_ERR', e.message.slice(0, 200)));
  await page.goto('https://arcadespot.com/game/dig-dug/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(6000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game"), [id*=play]').first();
  try { if (await playBtn.count()) { await playBtn.click({ timeout: 8000 }); } } catch (e) {}
  await page.waitForTimeout(9000);
  const info = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const gm = E.gameManager;
    const keys = Object.keys(gm).filter((k) => /paus|speed|fast|frame|run|play/i.test(k));
    const keysE = Object.keys(E).filter((k) => /paus|speed|fast|frame|run|play/i.test(k));
    return {
      gmPauseKeys: keys,
      EPauseKeys: keysE,
      gmPaused: gm.paused,
      EPaused: E.paused,
      coreConfig: (E.moduleConfig || E.module || {}).opts ? Object.keys((E.module || {}).opts || {}).slice(0, 20) : null,
    };
  });
  console.log(JSON.stringify(info, null, 2));
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });