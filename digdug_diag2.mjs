import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const tesseractPath = 'C:/Program Files/Tesseract-OCR';

function ocrPng(name, box) {
  try {
    const env = { ...process.env, PATH: `${tesseractPath};${process.env.PATH || ''}` };
    const out = execFileSync(venvPy, [ 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py', `${tmp}/${name}.png` ], { env, encoding: 'utf8', timeout: 20000 });
    console.log(`OCR[${name}]: ${out.trim()}`);
  } catch (e) {
    console.log(`OCR_FAIL[${name}]: ${e.message.slice(0, 120)}`);
  }
}

async function cropAndOcr(page, canvas, name) {
  const box = await canvas.boundingBox();
  if (!box) { console.log(`NO BOX ${name}`); return; }
  const shot = await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } });
  fs.writeFileSync(`${tmp}/${name}.png`, shot);
  ocrPng(name, box);
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
  await cropAndOcr(page, canvas, 'dd_boot_plain');

  // Start attempts spread out to let the ROM boot fully
  for (const k of ['Enter']) { await page.keyboard.press(k); await page.waitForTimeout(1500); }
  await cropAndOcr(page, canvas, 'dd_enter1');

  await page.keyboard.press('Enter'); await page.waitForTimeout(1500);
  await cropAndOcr(page, canvas, 'dd_enter2');

  // If still title, try Z then X (A/B)
  await page.keyboard.press('Z'); await page.waitForTimeout(1200);
  await cropAndOcr(page, canvas, 'dd_z');

  await page.keyboard.press('X'); await page.waitForTimeout(1200);
  await cropAndOcr(page, canvas, 'dd_x');

  // Drive a few moves
  for (const k of ['ArrowDown','ArrowDown','ArrowLeft','ArrowLeft']) { await page.keyboard.press(k); await page.waitForTimeout(400); }
  await cropAndOcr(page, canvas, 'dd_driven');
} catch (e) {
  console.log('DIAG_ERR:', e.message.slice(0, 200));
} finally {
  await browser.close();
}