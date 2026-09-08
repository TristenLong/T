import { chromium } from 'playwright';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';

async function main() {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.on('pageerror', (e) => console.log('PAGE_ERR', e.message.slice(0, 150)));
  await page.goto('https://arcadespot.com/game/dig-dug/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(6000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game"), [id*=play]').first();
  try { if (await playBtn.count()) { await playBtn.click({ timeout: 8000 }); } } catch (e) {}
  await page.waitForTimeout(10000);

  const out = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const gm = E.gameManager;
    const res = { gmProto: [], cycleKeys: [], members: {} };
    let o = gm;
    for (let i = 0; i < 4 && o; i++) { res.gmProto.push(Object.getOwnPropertyNames(o)); o = Object.getPrototypeOf(o); }
    for (const k of Object.keys(gm)) {
      const v = gm[k];
      res.members[k] = typeof v === 'function' ? 'fn' : typeof v;
    }
    // look for names suggesting state save/load / pause / running
    res.cycleKeys = Object.keys(gm).filter((k) => /state|sav|load|pause|run|resum|frame|step/i.test(k));
    // GAME_MANAGER / stateMenu references
    res.stateMenu = Object.keys(gm).filter((k) => /state|menu|save|load/i.test(k));
    return res;
  });
  console.log(JSON.stringify(out, null, 2).slice(0, 4000));

  const fnSrc = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const gm = E.gameManager;
    const collect = {};
    for (const k of ['loadState', 'getState', 'togglePlaying', 'toggleFastForward', 'restart']) {
      try { if (typeof gm[k] === 'function') collect[k] = gm[k].toString().slice(0, 900); } catch (e) { collect[k] = 'ERR ' + e.message; }
    }
    return collect;
  });
  console.log('--- loadState src ---');
  console.log(fnSrc.loadState);
  console.log('--- getState src ---');
  console.log(fnSrc.getState);
  console.log('--- togglePlaying src ---');
  console.log(fnSrc.togglePlaying);
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });