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
  if (await playBtn.count()) { await playBtn.click({ timeout: 10000 }); }
  await page.waitForTimeout(9000);
  const bind = await page.evaluate(() => {
    const M = window.EJS_emulator.Module;
    window.__SIM3 = M.cwrap('_simulate_input', 'null', ['number', 'number', 'number']);
    const r = {};
    for (const k of ['_cmd_save_state', '_load_state', '_simulate_input', 'cmd_save_state', 'load_state']) {
      const v = M[k];
      r[k + '.typeof'] = typeof v;
      if (typeof v === 'function') { try { r[k + '.src'] = String(v).slice(0, 80); } catch (e) {} }
    }
    // check if M._cmd_save_state is a heap function pointer vs direct
    r.hasAsmExports = !!(M.asm && typeof M.asm.cwrap === 'function');
    r.asmKeys = M.asm ? Object.keys(M.asm).filter((x) => /state|save|load|simulate/.test(x)).slice(0, 30) : [];
    return r;
  });
  console.log('BIND:', JSON.stringify(bind, null, 2));

  const press = async (b, holdMs) => {
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 1); } catch (e) {} }, b);
    await page.waitForTimeout(holdMs);
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 0); } catch (e) {} }, b);
    await page.waitForTimeout(400);
  };
  for (let i = 0; i < 6; i++) await press(3, 400);
  await page.waitForTimeout(1000);
  await press(7, 800);
  await shot('dd_sl_before');

  // Try direct-export call for save/load; fall back to asm exports
  const callSave = await page.evaluate(async () => {
    const M = window.EJS_emulator.Module;
    const out = {};
    try { await M['_cmd_save_state'](1); out.A = 'ok'; } catch (e) { out.A = 'ERR ' + String(e).slice(0, 100); }
    return out;
  });
  console.log('SAVE TRY:', JSON.stringify(callSave));
  await press(5, 600); await press(5, 600); await press(6, 700);
  await shot('dd_sl_after_move');

  const callLoad = await page.evaluate(async () => {
    const M = window.EJS_emulator.Module;
    const out = {};
    try { await M['_load_state'](1); out.A = 'ok'; } catch (e) { out.A = 'ERR ' + String(e).slice(0, 100); }
    return out;
  });
  console.log('LOAD TRY:', JSON.stringify(callLoad));
  await page.waitForTimeout(800);
  await shot('dd_sl_after_load');
  console.log('DONE');
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}