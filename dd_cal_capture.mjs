import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const tesseractPath = 'C:/Program Files/Tesseract-OCR';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';

const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--start-fullscreen', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const env = { ...process.env, PATH: `${tesseractPath};${process.env.PATH || ''}` };
const ocrOf = (png) => { const o = execFileSync(venvPy, [ocrPy, png], { env, encoding: 'utf8', timeout: 20000 }); const m = o.match(/TEXT=([^\n]*)/); return m ? m[1].trim() : ''; };

try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  const playBtn = page.locator('.as-play-col, a:text("Play Game"), button:text("Play Game")').first();
  if (await playBtn.count()) { await playBtn.click({ timeout: 10000 }); console.log('CLICKED PLAY'); }
  await page.waitForTimeout(9000);
  const canvas = page.locator('canvas.ejs_canvas, canvas').first();
  const box = await canvas.boundingBox();
  await page.evaluate(() => { window.__SIM3 = window.EJS_emulator.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']); });
  const press = async (b, holdMs) => {
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 1); } catch (e) {} }, b);
    await page.waitForTimeout(holdMs);
    await page.evaluate((bb) => { try { window.__SIM3(0, bb, 0); } catch (e) {} }, b);
    await page.waitForTimeout(400);
  };
  // start game
  await press(3, 400);
  await page.waitForTimeout(1200);
  // verify gameplay via OCR: pole for a frame whose OCR contains gameplay HUD but not title
  let ok = false;
  for (let i = 0; i < 10; i++) {
    const shot = await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } });
    const p = `${tmp}/dd_cal_verify.png`;
    fs.writeFileSync(p, shot);
    const t = ocrOf(p);
    console.log('verify', i, JSON.stringify(t.slice(0, 60)));
    if (t && !/1 PLAYER/.test(t) && /SCORE/i.test(t)) { ok = true; break; }
    await page.waitForTimeout(1000);
  }
  // dig right a couple tiles to create a tunnel
  await press(7, 700); // RIGHT
  await press(7, 700);
  await press(6, 300); // LEFT a bit
  await page.waitForTimeout(500);
  const shot = await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } });
  const pf = `${tmp}/dd_cal_playfield.png`;
  fs.writeFileSync(pf, shot);
  console.log('SAVED dd_cal_playfield.png', shot.length, 'ok=', ok);
} catch (e) {
  console.log('ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}