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
    // DFS a bounded window graph for an object that has getState + simulateInput
    const seen = new Set();
    const queue = [window];
    seen.add(window);
    let found = null;
    const describe = (o) => {
      const k = Object.keys(o).slice(0, 200);
      const has = (n) => typeof o[n] === 'function';
      return { keys: k.length, hasGetState: has('getState'), hasSim: has('simulateInput'), hasLoadState: has('loadState'), hasFF: has('toggleFastForward'), hasScreenshot: has('screenshot'), hasSave: has('quickSave'), ctor: o.constructor ? (o.constructor.name || 'anon') : 'none' };
    };
    queue: for (let i = 0; i < queue.length && i < 300; i++) {
      const o = queue[i];
      let inf;
      try { inf = describe(o); } catch (e) { continue; }
      if (inf.hasGetState && inf.hasSim) { found = o; break; }
      for (const key of Object.keys(o).slice(0, 80)) {
        try {
          const v = o[key];
          if (v && typeof v === 'object' && !seen.has(v)) { seen.add(v); queue.push(v); }
        } catch (e) {}
      }
    }
    if (found) {
      out.found = true;
      const d = describe(found);
      out.desc = d;
      out.sampleKeys = Object.keys(found).slice(0, 30);
      // Dump getState()
      try {
        const st = found.getState();
        out.stateByteLen = st ? st.byteLength : 0;
        out.stateType = st ? st.constructor.name : null;
      } catch (e) { out.getStateErr = String(e).slice(0, 120); }
    } else {
      out.found = false;
    }
    return out;
  });
  console.log(JSON.stringify(info, null, 2));
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}