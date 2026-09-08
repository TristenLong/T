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
    const M = window.EJS_emulator.Module;
    window.__SIM3 = M.cwrap('_simulate_input', 'null', ['number', 'number', 'number']);
    window.__LOAD = M.cwrap('_load_state', 'number', ['string', 'number']);
    window.__FF = M.cwrap('_toggle_fastforward', 'null', ['number']);
  });
  const press = async (b, holdMs) => {
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 1); } catch (e) {} }, b);
    await page.waitForTimeout(holdMs);
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 0); } catch (e) {} }, b);
    await page.waitForTimeout(400);
  };
  for (let i = 0; i < 6; i++) await press(3, 400);
  await page.waitForTimeout(1000);
  // check getState availability
  const st = await page.evaluate(() => {
    const M = window.EJS_emulator.Module;
    const out = { hasGet: typeof M.EmulatorJSGetState, hasFS: typeof M.FS, hasWrite: typeof M.FS?.writeFile };
    try {
      const b = M.EmulatorJSGetState();
      out.bufLen = b?.byteLength || 0;
      out.isU8 = b?.constructor?.name;
      window.__STATE1 = b; // stash in page
    } catch (e) { out.err = String(e).slice(0, 120); }
    return out;
  });
  console.log('GETSTATE:', JSON.stringify(st));
  await press(7, 800); // move right
  await shot('dd_gs_move');

  // now LOAD state1 we captured BEFORE moving
  const ld = await page.evaluate(async () => {
    const M = window.EJS_emulator.Module;
    const out = {};
    try {
      M.FS.unlink('/game.state');
    } catch (e) {}
    try {
      M.FS.writeFile('/game.state', window.__STATE1);
      out.wrote = true;
    } catch (e) { out.writeErr = String(e).slice(0, 100); }
    try {
      window.__LOAD('/game.state', 0);
      out.loaded = true;
    } catch (e) { out.loadErr = String(e).slice(0, 100); }
    await new Promise((r) => setTimeout(r, 500));
    return out;
  });
  console.log('LOAD:', JSON.stringify(ld));
  await page.waitForTimeout(500);
  await shot('dd_gs_load');
  console.log('shot after load');

  // fast-forward test
  const ff = await page.evaluate(() => { window.__FF(1); return 'ff on'; });
  console.log('FF:', ff);
  await page.waitForTimeout(2000);
  const ff2 = await page.evaluate(() => { window.__FF(0); return 'ff off'; });
  console.log('FF2:', ff2);
  await shot('dd_gs_ff');
  console.log('DONE');
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}