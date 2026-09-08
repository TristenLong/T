import { chromium } from 'playwright';

const url = process.argv[2] || 'https://arcadespot.com/game/dig-dug/';
const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:/Users/trist/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe',
});
const page = await browser.newPage();
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(6000);
  console.log('TITLE:', await page.title());

  // Wait for the page to settle; many arcade sites lazy-load the iframe.
  await page.waitForTimeout(6000);

  const info = await page.evaluate(() => {
    const out = { frames: [] };
    const frames = Array.from(document.querySelectorAll('iframe'));
    out.frames = frames.map((f, i) => ({
      i,
      src: (f.getAttribute('src') || '').slice(0, 200),
      cls: f.className,
      id: f.id,
      w: f.clientWidth,
      h: f.clientHeight,
      allow: f.getAttribute('allow'),
    }));
    // visible text snippet
    out.bodyText = (document.body.innerText || '').slice(0, 500);
    out.canvases = document.querySelectorAll('canvas').length;
    out.plays = Array.from(document.querySelectorAll('button,[class*=play i],[class*=start i]'))
      .map(b => ({ text: (b.innerText || '').slice(0, 20), cls: (b.className || '').slice(0, 40) }))
      .slice(0, 15);
    return out;
  });
  console.log('BODY TEXT:', JSON.stringify(info.bodyText));
  console.log('CANVASES:', info.canvases);
  console.log('IFRAMES:', JSON.stringify(info.frames, null, 2));
  console.log('PLAY BUTTONS:', JSON.stringify(info.plays, null, 2));

  // Color/blankness of the center region of the page — detects a canvas game.
  const shot = await page.screenshot({ path: 'C:/Users/trist/AppData/Local/Temp/opencode/play_probe.png' });
  console.log('SHOT_BYTES:', shot.length);

  console.log('\n--- CLICKING PLAY GAME ---');
  const playSel = '.as-play-col, button:text("Play Game"), a:text("Play Game")';
  const playBtn = page.locator(playSel).first();
  const cnt = await playBtn.count();
  console.log('play targets found:', cnt);
  if (cnt > 0) {
    await playBtn.click({ timeout: 10000 });
    await page.waitForTimeout(10000);
    console.log('after click TITLE:', await page.title());

    const emu = await page.evaluate(() => {
      const canvases = Array.from(document.querySelectorAll('canvas')).map((c) => ({
        id: c.id,
        cls: c.className,
        w: c.clientWidth,
        h: c.clientHeight,
        listeners: undefined,
        parentId: c.parentElement && c.parentElement.id,
        parentCls: c.parentElement && c.parentElement.className,
      }));
      // detect emulator: look at script src and global globals
      const scripts = Array.from(document.querySelectorAll('script[src]'))
        .map(s => s.src).filter(s => /emul|jnes|jsdos|dosbox|game|mame|nesstar|retro/i.test(s)).slice(0, 15);
      const winKeys = Object.keys(window).filter(k => /emul|game|jnes|nes|cri|cheat|simulate|pixel|nes\./i.test(k)).slice(0, 30);
      const attrs = Array.from(document.querySelectorAll('[id*=fceux],[id*=emulator],[id*=game],[class*=emulat]')).slice(0, 10).map(e => ({ tag: e.tagName, id: e.id, cls: e.className }));
      return { canvases, scripts, winKeys, attrs };
    });
    console.log('CANVAS INFO:', JSON.stringify(emu.canvases, null, 2));
    console.log('EMULATOR SCRIPTS:', JSON.stringify(emu.scripts));
    console.log('WINDOW KEYS:', JSON.stringify(emu.winKeys));
    console.log('EMU ELEMS:', JSON.stringify(emu.attrs));

    console.log('\n--- COIN + START + INPUT TEST ---');
    // Standard MAME/arcade bindings: 5=coin, 1=start, arrows=move, space=action
    for (const k of ['5', '5', '1']) {
      await page.keyboard.press(k);
      await page.waitForTimeout(400);
    }
    console.log('pressed coin+start');

    // Evaluate emulator state: is the game running? What does EJS expose?
    const state = await page.evaluate(() => {
      const out = { hasFocus: false, running: null, paused: null };
      try { out.hasFocus = window.EJS_GameManager && window.EJS_GameManager.hasFocus; } catch (e) {}
      try { out.running = window.EJS_emulator && window.EJS_emulator.getRuntime && window.EJS_emulator.getRuntime().core; } catch (e) {}
      try { out.gameName = window.EJS_gameName; } catch (e) {}
      try { out.settings = Object.keys(window.EJS_GameManager || {}).slice(0, 40); } catch (e) {}
      return out;
    });
    console.log('EMU STATE:', JSON.stringify(state));

    // Move for ~2s: hold keys so movement is registered
    for (const k of ['ArrowDown', 'ArrowLeft', 'ArrowDown', 'ArrowRight']) {
      await page.keyboard.down(k);
      await page.waitForTimeout(700);
      await page.keyboard.up(k);
    }
    console.log('movement keys sent');

    const shot3 = await page.screenshot({ path: 'C:/Users/trist/AppData/Local/Temp/opencode/play_probe_after_move.png' });
    console.log('SHOT_AFTER_MOVE:', shot3.length);

    // Try to read the EJS emulator's key thread / frame count to see if game is running
    const run2 = await page.evaluate(() => {
      const out = {};
      try { out.frameCount = window.EJS_emulator && window.EJS_emulator.getRuntime && window.EJS_emulator.getRuntime().getFramesCount ? window.EJS_emulator.getRuntime().getFramesCount() : 'n/a'; } catch (e) {}
      try { out.coreName = window.EJS_core || 'n/a'; } catch (e) {}
      return out;
    });
    console.log('FRAMES:', JSON.stringify(run2));

    console.log('\n--- CANVAS STATE PROBE ---');
    const canvasInfo = await page.evaluate(() => {
      const c = document.querySelector('canvas.ejs_canvas');
      if (!c) return { err: 'no canvas' };
      const ctx = c.getContext('2d');
      const img = ctx.getImageData(0, 0, c.width, c.height).data;
      let nonBlack = 0, lit = 0;
      const seen = new Set();
      for (let i = 0; i < img.length; i += 4) {
        const r = img[i], g = img[i+1], b = img[i+2];
        if (r > 10 || g > 10 || b > 10) nonBlack++;
        if (r > 128 && g > 128 && b > 128) lit++;
        seen.add((Math.round(r/32)<<6)|(Math.round(g/32)<<3)|Math.round(b/32));
      }
      const cw = c.width, ch = c.height;
      const rowSum = [];
      for (let y = 0; y < ch; y += 8) {
        let s = 0;
        for (let x = 0; x < cw; x += 4) {
          const i = (y * cw + x) * 4;
          s += (img[i] + img[i+1] + img[i+2]) / 3;
        }
        rowSum.push(s);
      }
      return { w: c.width, h: c.height, nonBlack, lit, uniqColors: seen.size, rowSum: rowSum.slice(0, 40) };
    });
    console.log('CANVAS STATE:', JSON.stringify(canvasInfo));

    const cshot = await page.evaluate(() => {
      const c = document.querySelector('canvas.ejs_canvas');
      return c ? c.toDataURL('image/png') : null;
    });
    if (cshot) {
      const fs = await import('fs');
      const b64 = cshot.split(',')[1];
      fs.writeFileSync('C:/Users/trist/AppData/Local/Temp/opencode/ejs_canvas.png', Buffer.from(b64, 'base64'));
      console.log('CANVAS WRITTEN len:', b64.length);
    } else {
      console.log('no canvas data');
    }
  } else {
    console.log('No Play Game button found');
  }
} catch (e) {
  console.log('PROBE_ERROR:', e.message);
} finally {
  await browser.close();
}
