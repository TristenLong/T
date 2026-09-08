import { chromium } from 'playwright';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const urls = [
  'https://www.retrogames.cc/embed/21051-dig-dug-japan.html',
  'https://www.retrogames.cc/nes-games/dig-dug-japan.html',
  'https://www.retrogames.cc/embed/33379-dig-dug-rev-2.html',
];

for (const url of urls) {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--disable-extensions'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  let crash = null;
  page.on('crash', () => { crash = 'crash'; });
  page.on('pageerror', (e) => { crash = `pageerror: ${String(e.message).slice(0, 80)}`; });
  page.on('close', () => { if (!crash) crash = 'closed'; });
  console.log(`\n=== ${url.split('/')[3]} | ${url} ===`);
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(8000);
    if (page.isClosed()) { console.log('page closed during load'); await browser.close(); continue; }
    let info = null;
    for (let i = 0; i < 45; i++) {
      info = await page.evaluate(() => {
        const keys = Object.keys(window).filter((k) => /EJS|_emulator|Module|nanogl|RA/i.test(k));
        return {
          keys: keys.slice(0, 30),
          canvas: !!document.querySelector('canvas.ejs_canvas'),
          anyCanvas: !!document.querySelector('canvas'),
          EJS_emulator: typeof (window.EJS_emulator || {}) ,
          gm: !!(window.EJS_emulator && window.EJS_emulator.gameManager),
        };
      }).catch((e) => ({ err: String(e).slice(0, 80), keys: [], canvas: false, anyCanvas: false, EJS_emulator: 'n/a', gm: false }));
      if (info && info.gm) break;
      await sleep(2000);
    }
    console.log('globals:', JSON.stringify(info).slice(0, 700));
    if (info && info.gm) {
      const inner = await page.evaluate(() => {
        const E = window.EJS_emulator;
        const mod = E.Module;
        let sim = null, f1 = null;
        try { sim = typeof mod.cwrap('simulate_input', 'null', ['number', 'number', 'number']); } catch (e) {}
        try { f1 = E.gameManager.getFrameNum(); } catch (e) {}
        return {
          sim_input: sim,
          frame: f1,
          gmMethods: Object.keys(E.gameManager).filter((k) => /State|FF|load|save|Main/i.test(k)),
          ejsVersion: E.version || null,
        };
      }).catch((e) => ({ innerErr: String(e).slice(0, 120) }));
      console.log('inner:', JSON.stringify(inner));
    }
  } catch (e) {
    console.log('probe error:', String(e).split('\n')[0].slice(0, 120));
  }
  await sleep(1000);
  console.log('crash:', crash);
  try { await browser.close(); } catch (e) {}
  await sleep(2000);
}