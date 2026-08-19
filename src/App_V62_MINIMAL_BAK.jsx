import React, { useState, useEffect } from 'react';

function App() {
  const [syncStatus, setSyncStatus] = useState('ATTEMPTING_SYNC...');
  const [vitals, setVitals] = useState(null);

  useEffect(() => {
    const checkSync = async () => {
      try {
        const res = await fetch('/api/pulse');
        const data = await res.json();
        setVitals(data);
        setSyncStatus('SYNC_ESTABLISHED_V62.1');
      } catch (e) {
        setSyncStatus('SYNC_FAILED: ' + e.message);
      }
    };
    checkSync();
    const interval = setInterval(checkSync, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{
      backgroundColor: '#000', color: '#00FF41', height: '100vh', width: '100vw',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'monospace', fontSize: '1.2rem', textAlign: 'center'
    }}>
      <h1 style={{ letterSpacing: '10px' }}>JESTER_V62.1_OMNISCIENCE</h1>
      <div style={{ margin: '20px', padding: '20px', border: '1px solid #00FF41' }}>
        STATUS: {syncStatus}<br/>
        {vitals && `CORE_LOAD: ${vitals.cpu}% | RAM_SYNC: ${vitals.ram}%`}
      </div>
      <div style={{ opacity: 0.5, fontSize: '0.8rem' }}>
        IF STATUS IS FAILED: ENSURE BACKEND IS RUNNING ON PORT 5000.<br/>
        IF STATUS IS ATTEMPTING: VITE PROXY MAY BE UNRESPONSIVE.
      </div>
    </div>
  );
}

export default App;
