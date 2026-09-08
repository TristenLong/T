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
    const M0 = window.EJS_emulator ? window.EJS_emulator.Module : null;
    const out = { hasModule: !!M0 };
    if (!M0) return out;
    // scan 3 levels deep for objects whose .Module === M0
    const seen = new Set();
    const queue = [window];
    seen.add(window);
    let found = null;
    for (let i = 0; i < queue.length && !found && i < 5000; i++) {
      const o = queue[i];
      let m;
      try { m = o.Module; } catch (e) {}
      if (m && m === M0 && typeof o.simulateInput === 'function') { found = o; break; }
      let keys;
      try { keys = Object.keys(o); } catch (e) { continue; }
      for (const k of keys.slice(0, 100)) {
        try {
          const v = o[k];
          if (v && typeof v === 'object' && !seen.has(v)) { seen.add(v); queue.push(v); }
        } catch (e) {}
      }
    }
    if (found) {
      out.found = true;
      out.keys = Object.keys(found).slice(0, 40);
      out.ctor = found.constructor ? found.constructor.name : 'anon';
      out.hasQS = typeof found.quickSave;
      out.hasQL = typeof found.quickLoad;
      out.hasGet = typeof found.getState;
      out.hasFF = typeof found.toggleFastForward;
      out.fnKeys = found.functions ? Object.keys(found.functions) : [];
      // locate globally by walking a few likely names
      out.globals = {};
      for (const n of ['game', 'Game', '_gm', 'gm', 'emu', 'core', 'EJS_GameManager', 'gameManager', 'GameManager', 'Rm', 'nr']) {
        try { out.globals[n] = typeof window[n]; } catch (e) {}
      }
    } else {
      // also: maybe EJS_emulator itself ({Module, functions:...}) replaced with manager-like object
      out.ejsKeys = Object.keys(window.EJS_emulator);
      out.ejsHasSim = typeof window.EJS_emulator.simulateInput;
      out.ejsHasQS = typeof window.EJS_emulator.quickSave;
    }
    return out;
  });
  console.log(JSON.stringify(info, null, 2));
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}