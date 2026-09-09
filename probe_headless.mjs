import { chromium } from 'playwright';
import { execFileSync } from 'child_process';

const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const venvPy = 'C:/Users/trist/gemini-voice-assistant/.venv/Scripts/python.exe';
const tmp = 'C:/Users/trist/AppData/Local/Temp/opencode';
const exe = chromePath;
console.log('chrome:', exe);

const browser = await chromium.launch({ headless: true, executablePath: exe, args: ['--disable-gpu', '--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
await page.goto('http://127.0.0.1:8801/', { waitUntil: 'domcontentloaded', timeout: 60000 });
console.log('loaded, waiting for EJS canvas…');
let box = null;
for (let i = 0; i < 90 && !box; i++) {
  await page.waitForTimeout(2000);
  const cvs = page.locator('canvas.ejs_canvas, canvas#nes, canvas').first();
  if (await cvs.count()) {
    box = await cvs.boundingBox().catch(() => null);
    if (box) console.log(`canvas @ t+${(i + 1) * 2}s:`, JSON.stringify(box));
  }
}
if (!box) { console.log('no canvas ever'); await browser.close(); process.exit(1); }

// try to click the Start button
const btn = page.locator('button:has-text("Start Game"), .start-button, .ejs_start_button, .gamestarted button:has-text("Start")').first();
if (await btn.count()) { await btn.click().catch(() => {}); console.log('clicked start'); }
else console.log('no start button found');

for (let i = 0; i < 12; i++) {
  await page.waitForTimeout(3000);
  const png = tmp.replace(/\\/g, '/') + '/probe_hl_' + i + '.png';
  await page.screenshot({ path: png, clip: { x: Math.round(box.x), y: Math.round(box.y), width: Math.round(box.width), height: Math.round(box.height) } }).catch(() => {});
  let out = '';
  try {
    out = execFileSync(venvPy, ['C:/Users/trist/gemini-voice-assistant/dd_diff.py', png.replace(/\//g, '\\'), 'json'], { encoding: 'utf8', timeout: 20000 }).trim();
  } catch (e) { out = 'ERR ' + String(e.message || e).slice(0, 60); }
  let ent = null;
  try { ent = JSON.parse(out); } catch (e) {}
  const p = ent && ent.basePlayer;
  const foes = ent && ent.baseEnemies ? ent.baseEnemies.length : '?';
  console.log(`t+${(i + 1) * 3}s p=${p ? p.map(v => Math.round(v)).join(',') : 'null'} foes=${foes} attractTop=${ent ? ent.attractTop : '?'} bright=${ent ? ent.bright : '?'} dark=${ent ? ent.dark : '?'}`);
}

await browser.close();
console.log('done');