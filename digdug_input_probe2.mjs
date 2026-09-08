import { chromium } from 'playwright';
import fs from 'fs';
import { execFileSync } from 'child_process';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/GOD_HAND_CORE/.venv/Scripts/python.exe';
const ocrPy = 'C:/Users/trist/gemini-voice-assistant/ocr_crop.py';
const tesseractPath = 'C:/Program Files/Tesseract-OCR';

function ocrPng(name) {
  try {
    const env = { ...process.env, PATH: `${tesseractPath};${process.env.PATH || ''}` };
    const out = execFileSync(venvPy, [ocrPy, `${tmp}/${name}.png`], { env, encoding: 'utf8', timeout: 25000 });
    const m = out.match(/TEXT=([^\n]*)/);
    console.log(`OCR[${name}]: ${m ? m[1].trim().slice(0, 90) : ''}`);
  } catch (e) { console.log(`OCR_FAIL[${name}]`); }
}

async function crop(page, canvas, name) {
  const box = await canvas.boundingBox();
  if (!box) return;
  fs.writeFileSync(`${tmp}/${name}.png`, await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } }));
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
  await canvas.click({ position: { x: 480, y: 240 } }).catch(() => {});

  // Dump the emulator's keyMap and make plain names readable
  const dump = await page.evaluate(() => {
    const out = { keyMap: null, gm: null, gmProps: null, config: null };
    try {
      const km = window.EJS_emulator && window.EJS_emulator.keyMap;
      if (km) {
        out.keyMap = {};
        for (const btn of Object.keys(km)) {
          const arr = km[btn];
          out.keyMap[btn] = arr && arr.map ? arr.map(k => ({ key: k.key, keyCode: k.keyCode, code: k.code })) : arr;
        }
      }
    } catch (e) { out.keyMap = 'ER:' + e.message; }
    try {
      const gm = window.EJS_GameManager;
      out.gm = typeof gm === 'object' ? Object.getOwnPropertyNames(gm) : String(gm);
    } catch (e) { out.gm = 'ER:' + e.message; }
    try { out.config = window.EJS_emulator && window.EJS_emulator.config; } catch (e) { out.config = 'ER:' + e.message; }
    return out;
  });
  console.log('KMAP:', JSON.stringify(dump, null, 1).slice(0, 2500));

  // Try 1: repository of likely start bindings with CDP trusted keys
  const tryKeys = ['Enter', 'NumpadEnter', '5', '1', 'Shift', 'X', 'Z', ' ', 'Escape'];
  for (const k of tryKeys) {
    await page.keyboard.press(k);
    await page.waitForTimeout(450);
  }
  await crop(page, canvas, 'k_try_cdp');
  ocrPng('k_try_cdp');

  // Try 2: synthetic KeyboardEvents via evaluate (bypass trust — confirms listener wiring)
  const synth = await page.evaluate(() => {
    const codes = { Enter: 13, Shift: 16, X: 88, Z: 90, Space: 32, Digit1: 49, Digit5: 53, ArrowDown: 40 };
    const fired = [];
    for (const [k, code] of Object.entries(codes)) {
      const opts = { key: k === 'Space' ? ' ' : k.length === 1 ? k : k.toLowerCase(), code: k, keyCode: code, which: code, bubbles: true, cancelable: true };
      const ok1 = window.dispatchEvent(new KeyboardEvent('keydown', opts));
      const ok2 = window.dispatchEvent(new KeyboardEvent('keyup', opts));
      fired.push([k, ok1, ok2]);
      // wait loop inside evaluate (small sleeps)
      const t0 = Date.now(); while (Date.now() - t0 < 60) {}
    }
    return fired;
  });
  console.log('SYNTH_FIRED:', JSON.stringify(synth));
  await page.waitForTimeout(1000);
  await crop(page, canvas, 'k_try_synth');
  ocrPng('k_try_synth');

  // Try 3: if EJS has controller store, push a raw button via gamepad api
  const gp = await page.evaluate(() => {
    const g = window.GamepadHandler;
    return g ? Object.keys(g) : null;
  });
  console.log('GAMEPADHANDLER_KEYS:', JSON.stringify(gp));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 300));
} finally {
  await browser.close();
}