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
  const init = await page.evaluate(() => {
    const E = window.EJS_emulator;
    window.__GM = E.gameManager;
    window.__SIM3 = () => {}; // will set after
    window.__SIM3 = E.gameManager.Module.cwrap('_simulate_input', 'null', ['number', 'number', 'number']);
    return {
      qs: typeof E.gameManager.quickSave,
      ql: typeof E.gameManager.quickLoad,
      get: typeof E.gameManager.getState,
      load: typeof E.gameManager.loadState,
      ff: typeof E.gameManager.toggleFastForward,
      sim: typeof E.gameManager.simulateInput,
      fs: typeof E.gameManager.FS,
    };
  });
  console.log('GM:', JSON.stringify(init));
  const press = async (b, holdMs) => {
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 1); } catch (e) {} }, b);
    await page.waitForTimeout(holdMs);
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 0); } catch (e) {} }, b);
    await page.waitForTimeout(300);
  };
  for (let i = 0; i < 5; i++) await press(3, 400);
  await page.waitForTimeout(1200);

  // basic: quickSave slot 1 now
  const sv = await page.evaluate(() => { try { return window.__GM.quickSave(1); } catch (e) { return 'ERR ' + String(e).slice(0, 100); } });
  console.log('quickSave:', sv);
  await press(7, 700); await press(7, 700); await press(5, 500);
  await shot('dd_ql_move');
  const ld = await page.evaluate(() => { try { window.__GM.quickLoad(1); return 'ok'; } catch (e) { return 'ERR ' + String(e).slice(0, 100); } });
  console.log('quickLoad:', ld);
  await page.waitForTimeout(700);
  await shot('dd_ql_load');
  console.log('roundtrip shot done');

  // getState/loadState via bytes
  const st1 = await page.evaluate(() => { const b = window.__GM.getState(); window.__ST = b; return { n: b.byteLength, t: b.constructor.name }; });
  console.log('getState:', JSON.stringify(st1));
  await press(7, 500); await press(7, 500);
  await shot('dd_gs2_move');
  const ld2 = await page.evaluate(() => { try { window.__GM.loadState(window.__ST); return 'ok'; } catch (e) { return 'ERR ' + String(e).slice(0, 100); } });
  console.log('loadState:', ld2);
  await page.waitForTimeout(700);
  await shot('dd_gs2_load');
  console.log('DONE');
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}