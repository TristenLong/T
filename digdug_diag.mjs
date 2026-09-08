import { chromium } from 'playwright';
import fs from 'fs';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';

async function saveCanvas(page, name) {
  try {
    const data = await page.evaluate(() => {
      const c = document.querySelector('canvas.ejs_canvas');
      if (!c) return null;
      return c.toDataURL('image/png');
    });
    if (data) {
      fs.writeFileSync(`${tmp}/${name}.png`, Buffer.from(data.split(',')[1], 'base64'));
      console.log(`SAVED ${name}.png len=${data.length}`);
    } else {
      console.log(`NO CANVAS for ${name}`);
    }
  } catch (e) {
    console.log(`CANVAS_SAVE_FAIL ${name}: ${e.message.slice(0, 120)}`);
  }
}

const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--start-fullscreen', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(6000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game")').first();
  if (await playBtn.count()) {
    await playBtn.click({ timeout: 10000 });
    console.log('CLICKED PLAY');
  }
  await page.waitForTimeout(8000);
  await saveCanvas(page, 'digdug_t0_playclicked');

  // Screenshot whole page too (for OCR context of emulator region)
  await page.screenshot({ path: `${tmp}/digdug_t0_page.png` });
  console.log('SAVED digdug_t0_page.png');

  // Boot attempts: various NES start bindings
  for (const k of ['Enter', 'Enter']) { await page.keyboard.press(k); await page.waitForTimeout(600); }
  await saveCanvas(page, 'digdug_t1_enter');

  // try Z (A button / fire) and arrows to see if a player appears
  await page.keyboard.press('Z'); await page.waitForTimeout(400);
  for (const k of ['ArrowDown','ArrowDown','ArrowLeft','ArrowLeft','ArrowUp','ArrowUp','ArrowRight','ArrowRight']) {
    await page.keyboard.press(k); await page.waitForTimeout(300);
  }
  await saveCanvas(page, 'digdug_t2_moved');

  // Attract-mode movement: if the game auto-plays (attract), screenshots will change too.
  await page.waitForTimeout(2500);
  await saveCanvas(page, 'digdug_t3_attract_wait');

  // dump any EJS window keys and canvas element details
  const info = await page.evaluate(() => ({
    canvas: (() => { const c = document.querySelector('canvas'); return c ? { w: c.width, h: c.height, cls: c.className, parentCls: c.parentElement && c.parentElement.className } : null; })(),
    ejsKeys: Object.keys(window).filter(k => k.startsWith('EJS_')),
    core: window.EJS_core || null,
    gameUrl: window.EJS_gameUrl || null,
  }));
  console.log('INFO:', JSON.stringify(info, null, 2));
} catch (e) {
  console.log('DIAG_ERR:', e.message.slice(0, 200));
} finally {
  await browser.close();
}