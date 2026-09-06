globalThis.PUTER_QUIET = true;
if (typeof window !== 'undefined') {
  window.PUTER_QUIET = true;
}

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
