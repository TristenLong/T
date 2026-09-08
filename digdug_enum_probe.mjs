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

  // Which element does EJS think is "canvas"? Compare with the page canvas.
  const elDump = await page.evaluate(() => {
    const E = window.EJS_emulator;
    const out = { ejsCanvas: null, pageCanvas: null, src: null, mode: null };
    try {
      const ec = E.canvas;
      out.ejsCanvas = ec ? { tag: ec.tagName, id: ec.id, cls: ec.className, w: ec.width, h: ec.height } : null;
    } catch (e) { out.ejsCanvas = 'ERR:' + e.message; }
    try {
      const pc = document.querySelector('canvas.ejs_canvas');
      out.pageCanvas = pc ? { tag: pc.tagName, id: pc.id, cls: pc.className, w: pc.width, h: pc.height } : null;
    } catch (e) {}
    try { out.mode = E.EmulatorMode || E.settings?.mO; } catch (e) {}
    return out;
  });
  console.log('ELEMENTS:', JSON.stringify(elDump));

  const pressBtn = async (btn, holdMs) => {
    // sim(port, button, state)
    await page.evaluate((b) => { try { window.__SIM3 && window.__SIM3(0, b, 1); } catch (e) {} }, btn);
    await page.waitForTimeout(holdMs);
    await page.evaluate((b) => { try { window.__SIM3 && window.__SIM3(0, b, 0); } catch (e) {} }, btn);
    await page.waitForTimeout(700);
  };
  await page.evaluate(() => {
    const E = window.EJS_emulator;
    window.__SIM3 = E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']);
  });

  // Ensure we're on the title screen; wait for it (attract demo may show first).
  let t0 = await cropOcr(page, canvas, 'd0');
  console.log('T0:', t0.slice(0, 70));
  if (!/PLAYER/i.test(t0)) {
    // wait through a cycle up to ~25s
    for (let i = 0; i < 10; i++) { await page.waitForTimeout(2500); t0 = await cropOcr(page, canvas, 'd1'); if (/PLAYER/i.test(t0)) break; }
  }
  console.log('TITLE CONFIRMED:', t0.slice(0, 70));

  // Sweep EJS button enums; a quick switch to "ROUND" text = real start.
  const enums = [0, 2, 3, 4, 5, 6, 7, 8, 10, 11];
  for (const b of enums) {
    await pressBtn(b, 350);
    const after = await cropOcr(page, canvas, 'd_btn');
    const hasRound = /ROUND|RQND|R0ND|\bRO\b/i.test(after) && !/SCORE/i.test(after);
    console.log(`BTN=${b}: "${after.slice(0, 55)}" ${hasRound ? '<-- ROUND!' : ''}`);
    if (hasRound) break;
  }
  const final = await cropOcr(page, canvas, 'd_final');
  console.log('FINAL:', final.slice(0, 80));
} catch (e) {
  console.log('PROBE_ERR:', e.message.slice(0, 400));
} finally {
  await browser.close();
}