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

  // Dump the button map + canvas & elements wiring.
  const dump = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const out = { dropdown: {}, controls: null, ejs: null, hasStartOverlay: false, canvasTabIndex: null, canvasId: null };
    try {
      out.controls = Object.keys(E.controls || {}).slice(0, 60);
      const c = E.controls || {};
      if (c && c.buttons) out.buttons = Object.keys(c.buttons).slice(0, 60);
    } catch (e) {}
    try { out.defaultButtonOptions = JSON.stringify(E.defaultButtonOptions || null).slice(0, 900); } catch (e) {}
    try { out.defaultButtonAliases = JSON.stringify(E.defaultButtonAliases || null).slice(0, 900); } catch (e) {}
    try { out.elements = Object.keys(E.elements || {}).slice(0, 40); } catch (e) {}
    try {
      const cv = document.querySelector('canvas');
      out.canvasTabIndex = cv.getAttribute('tabindex');
      out.canvasId = cv.id;
    } catch (e) {}
    return out;
  });
  console.log('DUMP:', JSON.stringify(dump, null, 1).slice(0, 3000));

  // Try focus + trusted keys on canvas
  await page.evaluate(() => {
    const cv = document.querySelector('canvas');
    cv.focus();
    cv.setAttribute('tabindex', '0');
    cv.focus();
  });
  await page.waitForTimeout(500);
  for (const k of ['Enter', 'Enter', 'X', 'X']) {
    await page.keyboard.press(k);
    await page.waitForTimeout(600);
  }
  console.log('AFTER canvas.focus + Enter/X:', (await cropOcr(page, canvas, 'f_canvas')).slice(0, 80));

  // Try CDP raw dispatch on the canvas element with trusted flag off (isTrusted edge)
  await page.evaluate(() => {
    const cv = document.querySelector('canvas');
    for (const k of ['Enter', 'Enter']) {
      cv.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
      cv.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    }
  });
  console.log('AFTER synthetic on canvas:', (await cropOcr(page, canvas, 'f_synth')).slice(0, 80));

  // Check the gamepad/keyboard binding arrays EJS uses for nes
  const maps = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const out = {};
    try { out.keyboardKeys = JSON.stringify(E.keyboardKeys || null).slice(0, 1200); } catch (e) {}
    try { out.nesButtons = JSON.stringify(E.defaultButtonOptions && (E.defaultButtonOptions.nes || E.defaultButtonOptions.GENERIC)).slice(0, 1500); } catch (e) {}
    try { out.controlsObj = JSON.stringify(E.controls && E.controls.c || null).slice(0, 1200); } catch (e) {}
    return out;
  });
  console.log('MAPS:', JSON.stringify(maps, null, 1).slice(0, 2500));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 400));
} finally {
  await browser.close();
}