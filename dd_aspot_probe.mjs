import { chromium } from 'playwright';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--mute-audio', '--disable-extensions'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
let crash = null;
page.on('crash', () => { crash = 'CRASH'; });
page.on('pageerror', (e) => { crash = `pageerror:${String(e.message).slice(0, 60)}`; });
await page.goto('https://arcadespot.com/game/dig-dug/', { waitUntil: 'domcontentloaded', timeout: 60000 });
await sleep(8000);
// list clickable play-ish buttons
const allels = await page.evaluate(() => {
  const out = [];
  for (const el of document.querySelectorAll('button,a,[role=button]')) {
    const t = (el.innerText || el.title || '').trim().slice(0, 40);
    const cls = el.className && String(el.className).slice(0, 40);
    out.push(t + ' | ' + cls);
  }
  return out.slice(0, 25);
});
console.log('candidates:\n' + allels.join('\n'));
// try clicking common play buttons
for (const sel of ['a:text("Play")', 'button:text("Play")', 'a:text("Play Game")', '[class*="play"]', '#start']) {
  const loc = page.locator(sel).first();
  if (await loc.count()) { console.log('clicking', sel); await loc.click({ timeout: 5000 }).catch((e) => console.log('click err', String(e).slice(0, 80))); await sleep(3000); break; }
}
await sleep(15000);
if (page.isClosed()) { console.log('PAGE DEAD', crash); await browser.close(); process.exit(0); }
const probe = await page.evaluate(() => {
  const canvas = document.querySelector('canvas');
  const keys = Object.keys(window).filter((k) => /EJS|emu/i.test(k));
  const E = window.EJS_emulator || window.EJS || window.emulator || null;
  return {
    canvas: !!canvas,
    canvasBox: (() => { try { const b = canvas?.getBoundingClientRect(); return b ? Math.round(b.width) + 'x' + Math.round(b.height) : null; } catch (e) { return null; } })(),
    ejsKeys: keys.slice(0, 12),
    ejsType: typeof window.EJS_emulator,
    gm: !!(E && E.gameManager),
    gmState: !!(E && E.gameManager && E.gameManager.getState && E.gameManager.loadState),
    hasCwrap: !!(E && E.Module && E.Module.cwrap),
  };
});
console.log('probe:', JSON.stringify(probe));
console.log('crash:', crash);
await browser.close();