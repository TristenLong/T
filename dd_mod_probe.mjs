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
  await page.evaluate(() => { window.__SIM3 = window.EJS_emulator.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']); });
  const press = async (b, holdMs) => {
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 1); } catch (e) {} }, b);
    await page.waitForTimeout(holdMs);
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 0); } catch (e) {} }, b);
    await page.waitForTimeout(400);
  };
  for (let i = 0; i < 4; i++) await press(3, 400);
  await page.waitForTimeout(1200);

  const info = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const out = {};
    const mod = E.Module;
    // 1) enumerate all keys on Module (asm exports) that look save/state/speed/reset related
    out.moduleKeys = mod ? Object.keys(mod).filter((k) => /save|state|speed|reset|screenshot|simulate|load/i.test(k)).slice(0, 80) : [];
    out.moduleKeyCount = mod ? Object.keys(mod).length : 0;
    // 2) try cwrap for the candidates and see which return functions at creation
    out.cwrap = {};
    for (const k of out.moduleKeys.slice(0, 40)) {
      try {
        const fn = mod.cwrap(k, 'null', ['number', 'number', 'string']);
        out.cwrap[k] = typeof fn;
      } catch (e) {
        out.cwrap[k] = 'ERR';
      }
    }
    // 3) functions object after boot
    out.fnKeys = E.functions ? Object.keys(E.functions) : [];
    out.ejs_keys = mod ? Object.keys(mod).filter((k) => k.startsWith('ejs') || k.startsWith('_') && /state|save/.test(k)).slice(0, 40) : [];
    return out;
  });
  console.log(JSON.stringify(info, null, 2));
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}