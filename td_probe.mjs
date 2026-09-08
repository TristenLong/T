import { chromium } from 'playwright';
import { pathToFileURL } from 'url';
import path from 'path';

const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const FILE = pathToFileURL(path.resolve('digger_game.html')).href;

let pass = 0, fail = 0;
const check = (name, ok, extra = '') => {
  console.log((ok ? 'PASS' : 'FAIL') + '  ' + name + (extra ? '  [' + extra + ']' : ''));
  ok ? pass++ : fail++;
};

const launch = async () => {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--mute-audio', '--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 640, height: 520 } });
  let crash = null;
  page.on('crash', () => { crash = 'CRASH'; });
  page.on('pageerror', (e) => { crash = `pageerror:${String(e.message).slice(0, 80)}`; });
  return { browser, page, crash };
};

// ---- LEVEL 1: movement only ----
{
  const { browser, page, crash } = await launch();
  await page.goto(FILE + '?level=1', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(400);
  const s0 = await page.evaluate(() => window.__GG.state());
  check('L1 initial: col4/bottom, dig disabled', s0.col === 4 && s0.row === 7 && s0.movingEnabled && !s0.digEnabled, JSON.stringify({ c: s0.col, r: s0.row }));
  await page.evaluate(() => window.__GG.input('left'));
  await page.evaluate(() => window.__GG.dig());
  const s1 = await page.evaluate(() => window.__GG.state());
  check('L1 move left works (col 3)', s1.col === 3, `col=${s1.col}`);
  check('L1 dig is a no-op (cleared 0, row 7)', s1.cleared === 0 && s1.row === 7, `cleared=${s1.cleared} row=${s1.row}`);
  check('L1 no crash (movement only)', crash === null, crash || 'ok');
  console.log('crash L1:', crash);
  await browser.close();
}

// ---- LEVEL 3: move + dig combined, full clear => WON ----
{
  const { browser, page, crash } = await launch();
  await page.goto(FILE + '?level=3', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(400);
  const s0 = await page.evaluate(() => window.__GG.state());
  check('L3 initial: dig enabled, no enemies yet', s0.digEnabled && !s0.enemiesEnabled, JSON.stringify(s0));
  await page.evaluate(() => window.__GG.dig());
  const s1 = await page.evaluate(() => window.__GG.state());
  check('L3 dig: clears tile, +1 point, advances to row6', s1.cleared === 1 && s1.score === 1 && s1.row === 6, `cleared=${s1.cleared} score=${s1.score} row=${s1.row}`);
  check('L3 dig carved exit below (clearTile[7][4])', await page.evaluate(() => window.__GG.clear[7][4]) === true);

  // clear every column: on surface, dig straight up, walk back down the shaft
  await page.evaluate(() => window.__GG.input('down'));   // (no-op, already fell through? player is at row6, below open)
  for (let c = 0; c < 12; c++) {
    await page.evaluate(({ c }) => {
      const gg = window.__GG;
      let guard = 0;
      while (gg.state().col > c && guard++ < 12) gg.input('left');
      while (gg.state().col < c && guard++ < 12) gg.input('right');
      while (gg.state().row > 0 && guard++ < 12) gg.dig();
    }, { c });
    // walk back down the cleared shaft to the surface
    await page.evaluate(() => {
      const gg = window.__GG;
      let guard = 0;
      while (gg.state().row < 7 && guard++ < 12) gg.input('down');
    });
  }
  const f = await page.evaluate(() => window.__GG.state());
  check('L3 all 84 tiles cleared', f.cleared === 84, `cleared=${f.cleared}`);
  check('L3 score = 84 (1 per tile)', f.score === 84, `score=${f.score}`);
  check('L3 WON state reached', f.won === true, `won=${f.won}`);
  check('L3 no crash', crash === null, crash || 'ok');
  console.log('crash L3:', crash);
  await browser.close();
}

// ---- LEVEL 5: enemies drift + creep, live life system ----
{
  const { browser, page, crash } = await launch();
  await page.goto(FILE + '?level=5', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(400);
  const s0 = await page.evaluate(() => window.__GG.state());
  const e0 = JSON.stringify(s0.enemies);
  check('L5 initial: 3 enemies, lives 3', s0.enemiesEnabled && s0.enemies.length === 3 && s0.lives === 3, e0);
  await sleep(600);                       // ~1 drift tick
  const s1 = await page.evaluate(() => window.__GG.state());
  const e1 = JSON.stringify(s1.enemies);
  check('L5 enemies drift horizontally', e0 !== e1, `before=${e0} after=${e1}`);
  await sleep(2600);                      // ~2+ creep ticks
  const s2 = await page.evaluate(() => window.__GG.state());
  check('L5 enemy row crept downward (rows>0)', s2.enemies.some((e) => e.row > 0), JSON.stringify(s2.enemies));
  check('L5 no crash', crash === null, crash || 'ok');
  console.log('L5 final enemies:', JSON.stringify(s2.enemies));
  await browser.close();
}

console.log(`\nRESULT  ${pass} passed / ${fail} failed`);
process.exit(fail ? 1 : 0);