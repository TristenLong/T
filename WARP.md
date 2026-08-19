# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project overview

- Single-page React 18 application built with Vite (`vite` + `@vitejs/plugin-react`), derived from the standard React + Vite template.
- Frontend UI presents the "JESTER" / "MASTERMIND" voice assistant, combining a 3D neural core visualization with a console-style control surface.
- The app expects a separate backend service running on `http://127.0.0.1:5000` and accessed via `/api/*` routes through the Vite dev server proxy.

## Code architecture and structure

### Entry point and bootstrapping

- `src/main.jsx` is the React entry point. It:
  - Imports global styles from `src/index.css` (sets a black background and green text defaults).
  - Renders the root `<App />` component into the DOM element with id `root` inside `<React.StrictMode>`.

### Core application shell (`src/App.jsx`)

`App` is the central orchestrator for UI, state, and backend integration.

Key responsibilities and state:
- Voice interaction
  - Uses the browser Web Speech API (`window.SpeechRecognition` / `webkitSpeechRecognition`) for continuous speech recognition.
  - Streams interim transcripts into `transcript` state and submits finalized utterances directly to the chat handler.
  - Controls listening lifecycle via `recognitionRef`, `isListening`, and an `autoRestart` flag.
- Text-to-speech
  - Uses `window.speechSynthesis` with a single helper `speak(txt)` that manages `SpeechSynthesisUtterance` lifecycles and tracks `isSpeaking`.
- Backend connectivity and vitals
  - Periodically polls `/api/pulse` (every 3 seconds) to populate `vitals` ({ `cpu`, `ram`, `status`, `model`, `logic_core` }) and update a high-level `status` string.
  - Exposes a "Diagnostics" action (`runDiagnostics`) that queries `/api/pulse` once, builds a textual report, and displays it as an overlay.
- Chat and memory
  - `handleSend(msg)` POSTs to `/api/chat` with `{ message: msg }` and expects a JSON response containing `response`.
  - On success it updates `response`, speaks it via TTS, refreshes history, and resets status.
  - `fetchHistory()` calls `/api/history?limit=20` and stores the returned list in `history`. Each history item is expected to have at least `{ id, role, content, pinned? }`.
  - `togglePin(id, pinned)` POSTs to `/api/pin` with `{ id, pinned: !pinned }`, then refreshes history.
  - `purge()` POSTs to `/api/reset` (after user confirmation) to clear unpinned memory, then refreshes history and surfaces a status message.
- Command hub
  - `hubActions` defines a small set of canned commands (e.g., "SECURE", "SOLVE", "REPORT", "SEARCH") that are funneled through `handleSend` as prebuilt natural-language prompts.

Layout and layering:
- The main JSX tree composes three visual layers:
  - A full-screen `MatrixRain` background effect.
  - A full-screen `<Canvas>` from `@react-three/fiber` with a `PerspectiveCamera`, `Stars`, and the `JesterBrain` 3D object, wrapped in `Suspense`.
  - An overlay UI (`header`, sidebar memory panel, central response panel, and controls) positioned with absolute/flex layout and `pointerEvents` toggling so the 3D canvas remains interactive only where intended.

### 3D neural core (`src/JesterBrain.jsx`)

- Pure presentation component using `@react-three/fiber` and `@react-three/drei`:
  - Renders an outer `Icosahedron` with `MeshDistortMaterial` and an inner `TorusKnot` with `meshStandardMaterial`.
  - Uses `useFrame` to:
    - Continuously rotate both meshes.
    - Apply a pulsing scale based on `isSpeaking` / `isListening` (larger, more intense when speaking; subtly increased when listening).
    - Occasionally inject a small random rotation "glitch" on the outer shell for a jittery, alive effect.
- Receives `isSpeaking` / `isListening` as props from `App` so visual activity reflects the assistant state.

### Matrix background (`src/MatrixRain.jsx`)

- Renders a fixed-position `<canvas>` that fills the viewport and draws a continuous "Matrix rain" effect in `requestAnimationFrame`.
- Responds to window resize events by updating canvas dimensions.
- The `color` prop controls the non-head glyph color; the main app passes the green theme color to keep visuals consistent.

### Alternative / legacy UIs

- `src/App_V43_BAK.jsx` and `src/App_V62_MINIMAL_BAK.jsx` contain previous experimental versions of the UI:
  - `App_V43_BAK.jsx` shows a more elaborate 3D "OmnipresentCore" and Matrix effect, with a different layout and copy, but uses the same `/api/chat` and `/api/pulse` endpoints.
  - `App_V62_MINIMAL_BAK.jsx` is a minimal status dashboard around `/api/pulse`.
- Neither of these components is currently wired into `main.jsx`; they are useful references for design and behavior but not part of the active build.

### Styling

- `src/index.css` defines global base styles (zero body margin, system-UI font stack, black background, green foreground text, monospace code font).
- `src/App.css` is largely the default Vite React template styling and is not central to the current inline-styled MASTERMIND UI.

### Backend contract summary

The frontend assumes the presence of a backend reachable at `http://127.0.0.1:5000` with the following behaviors (inferred from usage):

- `GET /api/pulse`
  - Returns a JSON object with at least `cpu`, `ram`, `model`, and `logic_core` fields, used for vitals, status, and diagnostics.
- `GET /api/history?limit=20`
  - Returns an array of message objects with fields such as `id`, `role` ("user" or assistant), `content`, and `pinned`.
- `POST /api/chat`
  - Request body: `{ "message": string }`.
  - Response body: `{ "response": string }`, which is spoken via TTS and shown in the central panel.
- `POST /api/pin`
  - Request body: `{ "id": string | number, "pinned": boolean }`.
  - Used to toggle the `pinned` flag on history entries.
- `POST /api/reset`
  - No request body expected in the frontend.
  - Used to purge unpinned memory entries.

Any changes to backend response shapes should be coordinated with the assumptions above.

## Development commands

All commands below assume you are in the repository root (`gemini-voice-assistant`) and using Node/npm (a `package-lock.json` is present).

### Install dependencies

```bash
npm install
```

### Run the development server

Starts the Vite dev server (by default on `http://127.0.0.1:5173`), with `/api/*` proxied to `http://127.0.0.1:5000` as configured in `vite.config.js`.

```bash
npm run dev
```

Make sure the backend service is running on `127.0.0.1:5000` so `/api/chat`, `/api/history`, `/api/pulse`, `/api/pin`, and `/api/reset` resolve correctly during development.

### Build for production

Creates an optimized production build in the `dist` directory.

```bash
npm run build
```

### Preview the production build

Serves the contents of `dist` via Vite's preview server (useful for verifying the production build locally).

```bash
npm run preview
```

### Linting

ESLint is configured via `eslint.config.js` for JavaScript/JSX with React Hooks and React Refresh rules. A `lint` script is defined in `package.json` that runs ESLint with the flat config over the entire project:

```bash
npm run lint
```

If running the lint script fails due to missing ESLint-related packages (e.g., `eslint`, `@eslint/js`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, `globals`), ensure they are installed as devDependencies (see `devDependencies` in `package.json`) and rerun the command.

### Testing

Vitest is configured via the `test` block in `vite.config.js` and a setup file at `src/test/setupTests.js` that:
- Integrates `@testing-library/jest-dom` matchers for DOM assertions.
- Mocks `@react-three/fiber` and `@react-three/drei` so the 3D scene can be rendered in jsdom.

Basic example tests live alongside the app code (e.g., `src/App.test.jsx`).

Run the full test suite:

```bash
npm test
```

Run a single test file:

```bash
npm test -- src/App.test.jsx
```
