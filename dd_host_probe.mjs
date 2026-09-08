import { chromium } from 'playwright';
const chromePath = 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const urls = [
  ['arcadespot', 'https://arcadespot.com/game/dig-dug/'],
  ['arcadepot2', 'https://www.arcadepot.com/play/dig-dug/arcade-games'],
  ['virtualgames', 'https://www.virtualgamesofficial.com/play/dig-dug/'],
  ['tmpigs', 'https://play.retrogames.cc/embed/21051-dig-dug-japan.html'],
];

for (const [name, url] of urls) {
  const browser = await chromium.launch({ headless: false, executablePath: chromePath, args: ['--mute-audio', '--disable-extensions'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  let crash = null;
  page.on('crash', () => { crash = 'CRASH'; });
  page.on('pageerror', (e) => { crash = `pageerror:${String(e.message).slice(0, 60)}`; });
  page.on('close', () => { if (!crash) crash = 'CLOSED'; });
  console.log(`=== ${name} ${url} ===`);
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await sleep(45000);
    if (page.isClosed()) { console.log('dead during load:', crash); await browser.close().catch(()=>{}); continue; }
    console.log('frames:', JSON.stringify(page.frames().map((f) => ({ url: f.url().slice(0, 60), name: f.name() }))).slice(0, 400));
    // find EJS across frames
    let found = null;
    for (const frame of page.frames()) {
      const o = await frame.evaluate(() => {
        const E = window.EJS_emulator;
        if (!E || !E.gameManager || typeof E.Module?.cwrap !== 'function') return null;
        let sim = 'no'; try { sim = typeof E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']); } catch (e) {}
        const r = document.querySelector('canvas.ejs_canvas') || document.querySelector('canvas');
        let box = null; try { const b = r?.getBoundingClientRect(); if (b && b.width > 50) box = { x: b.x, y: b.y, w: b.width, h: b.height }; } catch (e) {}
        return { sim, gmState: !!(E.gameManager.getState && E.gameManager.loadState), frame: frame, box, frameNum: (() => { try { return E.gameManager.getFrameNum(); } catch (e) { return null; } })() };
      }).catch(() => null);
      if (o && o.sim === 'function') { found = o; found.frame = frame; break; }
    }
    if (!found) { console.log('no EJS binding. crash:', crash); await browser.close().catch(()=>{}); continue; }
    console.log('EJS:', JSON.stringify({ sim: found.sim, gmState: found.gmState, box: found.box, frameNum: found.frameNum }));
    // test START press + frame advance via the owning frame
    const f0 = await found.frame.evaluate(() => { try { return window.__FF; } catch (e) {} });
    await found.frame.evaluate(() => {
      const E = window.EJS_emulator;
      window.__S = E.Module.cwrap('simulate_input', 'null', ['number', 'number', 'number']);
      window.__G = E.gameManager;
      window.__FF = (v) => { try { E.gameManager.toggleFastForward(v); } catch (e) {} };
    });
    const a = await found.frame.evaluate(() => { try { return window.__G.getFrameNum(); } catch (e) { return null; } });
    // press A (8) / START (3) briefly
    await found.frame.evaluate(() => { try { window.__S(0, 3, 1); } catch (e) {} });
    await sleep(300);
    await found.frame.evaluate(() => { try { window.__S(0, 3, 0); } catch (e) {} });
    await sleep(3000);
    const b = await found.frame.evaluate(() => { try { return window.__G.getFrameNum(); } catch (e) { return null; } });
    // canvas bytes (state) query
    const st = await found.frame.evaluate(() => { try { const s = window.__G.getState(); return s ? s.length : 0; } catch (e) { return -1; } });
    console.log(`input test: frames ${a} -> ${b} (delta ${(b - a)}) bytes=${st} crash=${crash}`);
  } catch (e) {
    console.log('probe error:', String(e).split('\n')[0].slice(0, 110), 'crash=', crash);
  }
  await browser.close().catch(() => {});
  await sleep(1500);
}