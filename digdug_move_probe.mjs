import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';
const tesseractPath = 'C:/Program Files/Tesseract-OCR';
const chromePath2 = chromePath;

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

async function rgbStats(page, canvas) {
  // coarse pixel stats via a tiny read of the canvas region from the browser (2D context may be lost on WebGL) -> use screenshot path only
  return null;
}

const browser = await chromium.launch({ headless: false, executablePath: chromePath2, args: ['--start-fullscreen', '--disable-extensions'] });
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
    await page.waitForTimeout(350);
  };

  // Wait for title
  let t = '';
  for (let i = 0; i < 12; i++) { t = await cropOcr(page, canvas, 'v0'); if (/PLAYER/i.test(t)) break; await page.waitForTimeout(2000); }
  console.log('TITLE:', t.slice(0, 70));

  // START (3)
  await press(3, 300);
  console.log('AFTER START:', (await cropOcr(page, canvas, 'v_start')).slice(0, 70));

  // Dig DOWN for 1.5s; the player sprite digs into the dirt -> big pixel change
  await page.evaluate(() => { try { window.__SIM3(0, 5, 1); } catch (e) {} });  // down
  await page.waitForTimeout(1500);
  await page.evaluate(() => { try { window.__SIM3(0, 5, 0); } catch (e) {} });
  await page.waitForTimeout(400);
  const afterDown = await cropOcr(page, canvas, 'v_down');
  console.log('AFTER DOWN:', afterDown.slice(0, 70));

  // LEFT
  await page.evaluate(() => { try { window.__SIM3(0, 6, 1); } catch (e) {} });
  await page.waitForTimeout(1500);
  await page.evaluate(() => { try { window.__SIM3(0, 6, 0); } catch (e) {} });
  await page.waitForTimeout(400);
  console.log('AFTER LEFT:', (await cropOcr(page, canvas, 'v_left')).slice(0, 70));

  // PUMP via A(8) and B(0)
  await press(8, 400);
  await press(0, 400);
  console.log('AFTER PUMP:', (await cropOcr(page, canvas, 'v_pump')).slice(0, 70));

  // RIGHT + UP spiral to probe remaining enums quickly
  for (const b of [7, 4, 7, 4]) await press(b, 250);
  console.log('AFTER SPIRAL:', (await cropOcr(page, canvas, 'v_spiral')).slice(0, 70));

  // check score changed (real score cell) vs demo
  const final = await cropOcr(page, canvas, 'v_final');
  console.log('FINAL:', final.slice(0, 90));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 400));
} finally {
  await browser.close();
}