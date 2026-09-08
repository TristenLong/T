import { chromium } from 'playwright';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';

const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--start-fullscreen', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game")').first();
  if (await playBtn.count()) { await playBtn.click({ timeout: 10000 }); console.log('CLICKED PLAY'); }
  await page.waitForTimeout(9000);
  const info = await page.evaluate(() => {
    const out = {};
    // Find every object with a saveState/loadState function on the window graph.
    const names = new Set(['EJS_emulator', 'EJS_GameManager', 'game', 'module', 'Module']);
    out.gmClass = typeof window.EJS_GameManager;
    const proto = window.EJS_GameManager && window.EJS_GameManager.prototype;
    out.gmProto = proto ? Object.getOwnPropertyNames(proto).filter((n) => /save|load|state|reset|speed/i.test(n)) : [];
    // source of saveState/loadState
    for (const m of ['saveState', 'loadState', 'toggleSpeed', 'resetSettings']) {
      const fn = window.EJS_GameManager && window.EJS_GameManager.prototype[m];
      out[m] = fn ? String(fn).slice(0, 600) : null;
    }
    // find instance: look for any global whose constructor is EJS_GameManager
    try {
      for (const k of Object.keys(window)) {
        try {
          const v = window[k];
          if (v && typeof v === 'object' && v.constructor && String(v.constructor.name) === 'EJS_GameManager') { out.instanceKey = k; }
          if (v && typeof v === 'object' && v.Module && v.Module.asm) { out.moduleKey = k; }
        } catch (e) {}
      }
    } catch (e) { out.scanErr = String(e).slice(0, 100); }
    return out;
  });
  console.log(JSON.stringify(info, null, 2));
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}