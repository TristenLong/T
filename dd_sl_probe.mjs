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
  const probe = () => page.evaluate(() => {
    const E = window.EJS_emulator;
    const out = { fnKeys: E && E.functions ? Object.keys(E.functions) : null, gmKeys: null, globKey: window.EJS_gameKey || null };
    try { if (E.GameManager) out.gmKeys = Object.getOwnPropertyNames(E.GameManager.prototype); } catch (e) {}
    // Look for saveState / loadState on functions object
    if (E && E.functions) {
      out.saveState = typeof E.functions.saveState;
      out.loadState = typeof E.functions.loadState;
      out.saveStateDef = String(E.functions.saveState).slice(0, 160);
      out.loadStateDef = String(E.functions.loadState).slice(0, 160);
    }
    return out;
  });
  console.log('FULL PROBE:', JSON.stringify(await probe(), null, 2));

  await page.evaluate(() => { window.__SIM3 = window.EJS_emulator.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']); });
  const press = async (b, holdMs) => {
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 1); } catch (e) {} }, b);
    await page.waitForTimeout(holdMs);
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 0); } catch (e) {} }, b);
    await page.waitForTimeout(400);
  };
  // start game
  for (let i = 0; i < 5; i++) await press(3, 400);
  await page.waitForTimeout(1000);

  // Try save state (slot 0), move, reload, observe
  const trySave = await page.evaluate(async () => {
    const E = window.EJS_emulator;
    const r = {};
    try {
      if (typeof E.functions.saveState === 'function') { await E.functions.saveState(0); r.savedViaFn = true; }
    } catch (e) { r.saveFnErr = String(e).slice(0, 120); }
    try {
      const raw = E.Module.cwrap('ejs_saveState', 'null', ['number']);
      raw(0); r.savedViaRaw = true;
    } catch (e) { r.rawErr = String(e).slice(0, 120); }
    return r;
  });
  console.log('SAVE:', JSON.stringify(trySave));

  // deviate: move right a lot
  for (let i = 0; i < 3; i++) await press(7, 500);

  const tryLoad = await page.evaluate(async () => {
    const E = window.EJS_emulator;
    const r = {};
    try {
      if (typeof E.functions.loadState === 'function') { await E.functions.loadState(0); r.loadedViaFn = true; }
    } catch (e) { r.loadFnErr = String(e).slice(0, 120); }
    try {
      const raw = E.Module.cwrap('ejs_loadState', 'null', ['number']);
      raw(0); r.loadedViaRaw = true;
    } catch (e) { r.rawErr = String(e).slice(0, 120); }
    return r;
  });
  console.log('LOAD:', JSON.stringify(tryLoad));
  await page.waitForTimeout(600);
  // screenshot for diff later
  await page.screenshot({ path: 'C:/Users/trist/AppData/Local/Temp/opencode/dd_sl.png' });
  console.log('DONE round-trip');
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}