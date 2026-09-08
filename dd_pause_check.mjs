import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';

async function main() {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto('https://arcadespot.com/game/dig-dug/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(6000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game"), [id*=play]').first();
  try { if (await playBtn.count()) { await playBtn.click({ timeout: 8000 }); } } catch (e) {}
  await page.waitForTimeout(9000);
  await page.evaluate(() => {
    const E = window.EJS_emulator;
    window.__SIM3 = E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']);
    const gm = E.gameManager;
    window.__GM = gm; window.__FF = (v) => gm.toggleFastForward(v);
  });
  const canvas = page.locator('canvas.ejs_canvas, canvas#nes, canvas').first();
  const box = await canvas.boundingBox();
  const shot = async (name) => {
    const png = `${tmp}/${name}.png`;
    fs.writeFileSync(png, await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } }));
    return png;
  };
  const press = (b, ms) => page.evaluate((x) => { window.__SIM3(0, x, 1); }, b).then(() => page.waitForTimeout(ms)).then(() => page.evaluate((x) => { window.__SIM3(0, x, 0); }, b));
  const diff = (ta, tb) => JSON.parse(execFileSync(venvPy, ['C:/Users/trist/gemini-voice-assistant/dd_diff.py', ta, tb], { encoding: 'utf8', timeout: 20000 }).trim());

  for (let b2 = 0; b2 < 8; b2++) { await press(3, 400); await press(8, 400); await page.waitForTimeout(1200); }
  await page.waitForTimeout(800);
  await page.evaluate(() => { window.__SAVED = window.__GM.getState(); });

  // 1) reload, wait 4s, diff: expect paused (no motion)
  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.waitForTimeout(1000);
  await shot('p_A'); await page.waitForTimeout(4000); await shot('p_B');
  console.log('paused-wait          :', JSON.stringify(diff(`${tmp}/p_A.png`, `${tmp}/p_B.png`).moving));

  // 2) reload, hold RIGHT 3s, diff: expect motion
  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.waitForTimeout(1000);
  await shot('m_A');
  await press(7, 3000);
  await shot('m_B');
  console.log('hold-right-3s        :', JSON.stringify(diff(`${tmp}/m_A.png`, `${tmp}/m_B.png`)));

  // 3) reload, hold RIGHT 3s WITH FF, diff: expect more motion if FF accelerates
  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.evaluate(() => { window.__FF(1); });
  await page.waitForTimeout(1000);
  await shot('f_A');
  await press(7, 3000);
  await shot('f_B');
  console.log('hold-right-3s-FF     :', JSON.stringify(diff(`${tmp}/f_A.png`, `${tmp}/f_B.png`)));
  await page.evaluate(() => { window.__FF(0); });

  // 4) also: does emulator advance at all after a press + release? (4s after a held release)
  await page.evaluate(() => { window.__GM.loadState(window.__SAVED); });
  await page.waitForTimeout(1000);
  await press(7, 200);
  await shot('q_A'); await page.waitForTimeout(4000); await shot('q_B');
  console.log('press-then-wait       :', JSON.stringify(diff(`${tmp}/q_A.png`, `${tmp}/q_B.png`).moving));
  await browser.close();
}
main().catch((e) => { console.error(e.message); process.exit(1); });