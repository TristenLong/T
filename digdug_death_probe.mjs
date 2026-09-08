import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';
const tesseractPath = 'C:/Program Files/Tesseract-OCR';

async function cropOcr(page, canvas, name) {
  const box = await canvas.boundingBox();
  if (!box) return '';
  fs.writeFileSync(`${tmp}/${name}.png`, await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } }));
  try {
    const env = { ...process.env, PATH: `${tesseractPath};${process.env.PATH || ''}` };
    const out = execFileSync(venvPy, [ocrPy, `${tmp}/${name}.png`], { env, encoding: 'utf8', timeout: 25000 });
    const m = out.match(/TEXT=([^\n]*)/);
    return m ? m[1].trim() : '';
  } catch (e) { return ''; }
}

const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--start-fullscreen', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game")').first();
  if (await playBtn.count()) { await playBtn.click({ timeout: 10000 }); console.log('CLICKED PLAY'); }
  await page.waitForTimeout(9000);
  const canvas = page.locator('canvas.ejs_canvas, canvas').first();
  await page.evaluate(() => {
    window.__SIM3 = window.EJS_emulator.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']);
  });
  const press = async (b, holdMs) => {
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 1); } catch (e) {} }, b);
    await page.waitForTimeout(holdMs);
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 0); } catch (e) {} }, b);
  };

  // Wait for title screen
  let t = '';
  for (let i = 0; i < 12; i++) { t = await cropOcr(page, canvas, 'p_title'); if (/PLAYER/i.test(t)) break; await page.waitForTimeout(2000); }
  console.log('TITLE OK:', /PLAYER/i.test(t));

  // START with a firmer push
  await press(3, 500);
  await page.waitForTimeout(1500);
  console.log('POST-START:', (await cropOcr(page, canvas, 'p_start')).slice(0, 70));

  // Dig straight up for 8s (hold UP + pump) — enemies come down; head-on is fast death.
  await page.evaluate(() => { try { window.__SIM3(0, 4, 1); } catch (e) {} });
  await page.evaluate(() => { try { window.__SIM3(0, 8, 1); } catch (e) {} });
  await page.waitForTimeout(8000);
  await page.evaluate(() => { try { window.__SIM3(0, 4, 0); window.__SIM3(0, 8, 0); } catch (e) {} });
  console.log('AFTER UP-DIG:', (await cropOcr(page, canvas, 'p_updig')).slice(0, 70));

  // Then do nothing except watch; a REAL game can die -> GAME OVER / back to title.
  // Demo mode keeps autoplaying and never shows GAME OVER.
  let deathSeen = false;
  for (let i = 0; i < 14; i++) {
    await page.waitForTimeout(1000);
    const s = await cropOcr(page, canvas, 'p_watch');
    if (/GAME\s*OVER|GAMEOVER|LONELY|\bPLAYER\b.*NAMCO|ROUND\s*[1-9]/i.test(s)) {
      console.log(`watch ${i}: "${s.slice(0, 80)}"`);
      if (/GAME\s*OVER/i.test(s)) { deathSeen = true; console.log('*** GAME OVER SEEN (confirms real 1P game) ***'); break; }
    }
  }
  console.log('DEATH_SEEN:', deathSeen);

  // Manual d-pad sweep after any state to observe response re: live pit
  for (const b of [6,6,7,7]) { await press(b, 400); }
  console.log('POST SWEEP:', (await cropOcr(page, canvas, 'p_sweep')).slice(0, 70));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 400));
} finally {
  await browser.close();
}