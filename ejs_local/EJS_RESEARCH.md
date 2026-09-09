# EmulatorJS → JESTER research appendix

Sources and verified facts behind the "make the system work way better" work.
All API claims below were read directly from the EmulatorJS source (stable,
indexed 2026-03-11, commit `d15b63`).

## Source URLs

- DeepWiki API reference: https://deepwiki.com/EmulatorJS/EmulatorJS/8-api-reference
- DeepWiki self-hosting guide: https://deepwiki.com/EmulatorJS/EmulatorJS/6.2-self-hosting-guide
- DeepWiki input handling: https://deepwiki.com/EmulatorJS/EmulatorJS/4.2-input-handling-and-gamepad-support
- DeepWiki EJS_GameManager API: https://deepwiki.com/EmulatorJS/EmulatorJS/8.2-ejs_gamemanager-api
- Options / embed docs: https://emulatorjs.org/docs/options , https://emulatorjs.org/docs/getting-started
- Repo: https://github.com/EmulatorJS/EmulatorJS
- CDN (stable build): https://cdn.emulatorjs.org/stable/data/
- Game facts: https://en.wikipedia.org/wiki/Dig_Dug , https://digdug.fandom.com/wiki/Pooka
- Free browser mirrors: https://arcadespot.com/game/dig-dug/ (main agent target),
  https://www.retrogames.cc/arcade-games/dig-dug-rev-2.html (embed + ROM/files6 CDN),
  https://www.free80sarcade.com/digdug.php , https://freebie.games/games/dig-dug

## Verified EmulatorJS facts

### Core packaging (stable build, 4.x)
- `data/loader.js` is a bootstrap; it reads `EJS_pathtodata` and loads one
  `emulator.min.js` + `emulator.min.css` (production) OR individual `src/*` files
  (debug). Global config vars are read before the loader runs.
- Modern stable cores are a SINGLE packaged file:
  `data/cores/{core}{[-thread]}{[-legacy]}-wasm.data` (a 7z/zip archive whose
  `checkCompression()` unpacks into `*.wasm`, optionally `*.worker.js`, `*.js`,
  `core.json`, `build.json`, `license.txt`). For `EJS_core='arcade'` the first
  matching core is `fbneo` → `data/cores/fbneo-wasm.data` (8.3 MB). Do NOT look
  for separate `fbneo-wasm.js` / `.wasm` — they don't exist anymore.
- Decompression helpers are fetched on demand from `data/compression/`:
  `extract7z.js`, `extractzip.js`, `libunrar.js`, `libunrar.wasm`.
- Core reports (cache invalidation) live at `data/cores/reports/{core}.json`;
  missing → caching disabled with a console warning (harmless).

### Self-hosting checklist
1. `data/loader.js`, `data/emulator.min.js`, `data/emulator.min.css`
2. `data/cores/fbneo-wasm.data` (+ `data/cores/reports/fbneo.json` optional)
3. `data/compression/{extract7z,extractzip,libunrar}.js` + `libunrar.wasm`
4. ROM via `EJS_gameUrl`, BIOS via `EJS_biosUrl` (arcade: `arcade.7z`)
5. HTML: `EJS_player`, `EJS_pathtodata` (trailing slash), `EJS_core='arcade'`,
   `EJS_startOnLoaded=false` + agent clicks the "Start Game" button (a real
   trusted click, which also unlocks the AudioContext in headless Chrome —
   autoboot via `EJS_startOnLoaded=true` does NOT count as a user gesture).
6. Threading headers (COOP/COEP) only needed for threaded cores/ppsspp —
   fbneo runs fine without.

### Agent wiring (web_agent.mjs) for the harness
- `ensureLocalEjs()` spawns `ejs_local/serve_ejs.mjs` on 127.0.0.1:8801 on
  demand (port probe first, `node serve_ejs.mjs 8801` detached, 6s health poll).
- `clickEJSStart(page)` clicks the `Start Game` overlay button before the
  wait-for-EJS loop if `EJS_startOnLoaded=false` (mirrors the arcade-host Play
  CTA click); POST PETITION-style quick-loading fallbacks still need it so the
  canvas appears before the 80s wait window expires.
- Headless validation of rendering is unreliable (SwiftShader software GL +
  no audio device → boots in ~50s and sometimes never draws; headed Chrome
  boots in ~20s and always draws). Use headed validation (or the agent itself)
  as the oracle, not `dbg_deep.mjs`.

### Key APIs (all on `window.EJS_emulator` / `.gameManager`)
- `simulate_input` via `E.Module.cwrap('simulate_input','null',['number','number','number'])`
  → `(player, index, value)`; player 0-indexed, value 0/1. RetroArch indices:
  B=0, Y=1, Select=2, Start=3, Up=4, Down=5, Left=6, Right=7, A=8, X=9, L=10, R=11.
  (The agent's existing SIMBTN map already matches.)
- Reserved hotkey indices routed by GameManager, NOT the core:
  24=quick save, 25=quick load, 26=next save slot, 27=fast-forward,
  28=rewind (only if `rewindEnabled`), 29=slow motion.
- `gameManager.getState()` → Uint8Array; `loadState(state)` → restore;
  `quickSave(slot)` / `quickLoad(slot)` + `saveSaveFiles/loadSaveFiles/getSaveFile`.
- `gameManager.toggleFastForward(active)`, `setFastForwardRatio(r)`,
  `toggleSlowMotion(active)`, `setSlowMotionRatio(r)`, `toggleMainLoop(playing)`
  (playing=true resumes), `screenshot()` → Promise.
- Events: `'ready'`, `'start-clicked'`, `'start'`, `'exit'`, `'loadState'`,
  `'saveState'`, `'loadSave'`, `'saveSave'`. Register with `EJS_emulator.on(...)`.
  NOTE: on the arcadespot embed the game may start before we can attach → always
  keep an OCR fallback.
- Returning arrays crossing the Playwright boundary: keep the Uint8Array
  page-side (`window.__ST[k] = getState()`) instead of shipping megabytes of
  numbers through `evaluate`; `loadState(new Uint8Array(window.__ST[k]))`.

### Gotchas observed on the live arcade host
- EJS 4.x fast-forward/slow-motion paint an "= xx%" overlay and can freeze frames
  → OCR pollution; gate with config and auto-disable on overlay text.
- The "nothing is on screen" symptom was the EJS settings overlay
  (Fast-Forward / Speed Options / Keyboard Bindings text) — ESC closes it.
- Fygar (red dragon) still shares the player-red rule in dd_diff → full-array
  color diff only becomes robust when we own the frame (self-hosted harness).

## Local harness (this repo)

- `ejs_local/host_digdug.html` — autoboot Dig Dug (fbneo/arcade) at `/`.
- `ejs_local/data/` — EJS stable build + fbneo core + compression helpers.
- `ejs_local/serve_ejs.mjs` — node static server on 127.0.0.1:8801; proxies
  `/rom/digdug.zip` and `/bios/arcade.7z` same-origin from retrogames.cc/fire6.
- Start with: `node serve_ejs.mjs 8801` (any port; config g.url accordingly).
- Agent wiring: GAME_REGISTRY['dig-dug'].fallbackUrls last entry points at
  `http://127.0.0.1:8801/` so runs auto-fall over to it when remote hosts fail.

## web_agent.mjs levers implemented (mapping)

- `bindEJS()` now also installs `__SAVESLOT/__LOADSLOT` (page-side save-state
  store), `__SLOW` (slow-mo), `__PAUSE` (toggleMainLoop), and `EJS_emulator.on`
  'start'/'loadState' flags (`__EJSSTART`, `__EJSLOAD`).
- `runVisionSearch` (survival autopilot):
  - snapshots a fresh round-1 save state right after GAME STARTED;
  - on death (title seen): keep the Q-learning death punishment, then
    `loadState` back to the snapshot instead of the fragile OCR re-boot dance
    (config `g.useSavestates:false` to force the old key re-boot; falls back to
    key re-boot if restore fails);
  - `revive()` (page/EJS lost) restores the snapshot after re-bind instead of a
    full boot;
  - `g.slowMotion:true` engages slow-mo after boot and auto-disables when OCR
    sees the overlay (regex widened to Slow-Motion).