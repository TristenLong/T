globalThis.PUTER_QUIET = true;
if (typeof window !== 'undefined') {
  window.PUTER_QUIET = true;
}

// @react-three/fiber v9 still constructs THREE.Clock for its internal store
// (state.clock passed to useFrame) and three >= r183 emits a deprecation
// warning for it on every Canvas mount. It is a third-party deprecation we
// can't patch from here, so drop exactly that one line from the console
// before the app renders.
const _jesterWarn = console.warn;
console.warn = (...args) => {
  const first = args[0];
  if (typeof first === 'string' && first.indexOf('Clock: This module has been deprecated') !== -1) {
    return;
  }
  _jesterWarn.apply(console, args);
};

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
