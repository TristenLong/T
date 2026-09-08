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
    console.log(`OCR[${name}]: ${m ? m[1].trim() : ''}`);
  } catch (e) { console.log(`OCR_FAIL[${name}]: ${e.message.slice(0,120)}`); }
}

async function crop(page, canvas, name) {
  const box = await canvas.boundingBox();
  if (!box) return;
  const shot = await page.screenshot({ clip: { x: box.x, y: box.y, width: box.width, height: box.height } });
  fs.writeFileSync(`${tmp}/${name}.png`, shot);
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

  const probe = await page.evaluate(() => {
    const out = {};
    out.hasFocusDoc = document.hasFocus();
    out.active = document.activeElement && document.activeElement.tagName;
    out.ejsKeys = Object.keys(window).filter(k => k.startsWith('EJS_'));
    out.emulatorKeys = window.EJS_emulator ? Object.keys(window.EJS_emulator).slice(0, 60) : null;
    out.gmKeys = window.EJS_GameManager ? Object.keys(window.EJS_GameManager).slice(0, 60) : null;
    out.controller = window.EJS_controllerStore ? Object.keys(window.EJS_controllerStore).slice(0, 20) : null;
    // find a button map
    out.input = window.EJS_input ? Object.keys(window.EJS_input).slice(0, 40) : null;
    // look for any global containing "Numpad"/"Enter" mappings
    const hits = [];
    for (const k of Object.keys(window)) {
      try {
        const v = window[k];
        const s = typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v);
        if (s && s.includes('Numpad')) hits.push(k);
      } catch (e) {}
    }
    out.btnMapCandidates = hits.slice(0, 10);
    return out;
  });
  console.log('PROBE1:', JSON.stringify(probe, null, 1));

  // Try to focus the canvas target and confirm document focus
  await canvas.click({ position: { x: 480, y: 240 } });
  await page.evaluate(() => window.focus());
  const focus2 = await page.evaluate(() => ({ hasFocus: document.hasFocus(), active: document.activeElement && document.activeElement.tagName }));
  console.log('PROBE_FOCUS_AFTER_CLICK:', JSON.stringify(focus2));

  // Now try start sequence with focus confirmed
  for (const k of ['Enter']) { await page.keyboard.press(k); await page.waitForTimeout(1200); }
  await crop(page, canvas, 'inp_enter');
  ocrPng('inp_enter');

  await page.keyboard.press('Enter'); await page.waitForTimeout(1200);
  await crop(page, canvas, 'inp_enter2');
  ocrPng('inp_enter2');

  for (const k of ['5']) { await page.keyboard.press(k); await page.waitForTimeout(600); }
  await crop(page, canvas, 'inp_coin');
  ocrPng('inp_coin');

  for (const k of ['1']) { await page.keyboard.press(k); await page.waitForTimeout(600); }
  await crop(page, canvas, 'inp_1');
  ocrPng('inp_1');

  // dump the EJS keyboard wiring if any
  const wire = await page.evaluate(() => {
    const out = {};
    for (const k of ['EJS_emulator','EJS_GameManager','EJS_Runtime','EJS_controllerStore']) {
      if (window[k]) {
        try {
          const v = window[k];
          const keys = Object.keys(v);
          out[k] = keys.slice(0, 40);
        } catch (e) { out[k] = 'n/a'; }
      }
    }
    // NES mapping in core config?
    out.appleScript = window.appleScript === undefined ? 'none' : 'present';
    return out;
  });
  console.log('WIRE:', JSON.stringify(wire, null, 1));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 250));
} finally {
  await browser.close();
}