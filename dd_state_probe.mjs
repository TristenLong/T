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
  const q = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const out = { gm: typeof E?.GameManager, hasFunctions: !!(E && E.functions) };
    // enumerate EJS_emulator and GameManager prototype methods
    try {
      const gmProto = E.GameManager && E.GameManager.prototype;
      out.gmProto = gmProto ? Object.getOwnPropertyNames(gmProto).filter((n) => /state|save|load|screenshot|simulate|volume|reset|speed/i.test(n)) : [];
      out.funcKeys = E.functions ? Object.keys(E.functions).filter((n) => /state|save|load|screenshot|simulate|reset|speed/i.test(n)) : [];
      out.eKeys = Object.keys(E).filter((n) => /state|save|load|screenshot|simulate|reset|speed|core/i.test(n));
      // try to grab raw module funcs
      if (E.Module && E.Module.cwrap) {
        const t = ['simulate_input', 'ejs_saveState', 'ejs_loadState', 'cmd_take_screenshot', 'ejs_toggleSpeed', 'ejs_reset'];
        out.cwrapAvailable = {};
        for (const f of t) {
          try { const fn = E.Module.cwrap(f, 'null', ['number', 'number', 'string']); out.cwrapAvailable[f] = typeof fn === 'function'; } catch (e) { out.cwrapAvailable[f] = 'ERR:' + String(e).slice(0, 40); }
        }
      }
    } catch (e) { out.err = String(e).slice(0, 200); }
    return out;
  });
  console.log(JSON.stringify(q, null, 2));
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}