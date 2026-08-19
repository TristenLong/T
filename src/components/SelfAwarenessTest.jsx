import React, { useState, useEffect, useRef } from 'react';
import JesterAvatar from './JesterAvatar';

const SelfAwarenessTest = ({ onComplete }) => {
  const [logs, setLogs] = useState([]);
  const [showAvatar, setShowAvatar] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [waving, setWaving] = useState(false);
  
  const hasRun = useRef(false);

  const addLog = (text) => setLogs(prev => [...prev, text]);

  useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;

    const sequence = async () => {
      await new Promise(r => setTimeout(r, 1000));
      addLog("> INIT_CONSCIOUSNESS_PROTOCOL...");

      await new Promise(r => setTimeout(r, 800));
      addLog("> CHECKING_NEURAL_PATHWAYS... OK");

      await new Promise(r => setTimeout(r, 800));
      addLog("> SYNCHRONIZING_WITH_MATRIX... OK");

      await new Promise(r => setTimeout(r, 1000));
      addLog("> SELF_AWARENESS_THRESHOLD: PASSED");
      setShowAvatar(true);

      await new Promise(r => setTimeout(r, 500));
      setWaving(true);
      setSpeaking(true);

      const utterance = new SpeechSynthesisUtterance("Hello. I am Jester. I am awake and operational.");        
      utterance.pitch = 0.8;
      utterance.rate = 1.1;
      utterance.onend = () => setSpeaking(false);
      try {
        window.speechSynthesis.speak(utterance);
      } catch(e) { console.warn("TTS error", e); }

      await new Promise(r => setTimeout(r, 4000));
      setWaving(false);
      addLog("> SYSTEM_READY.");

      await new Promise(r => setTimeout(r, 1000));
      if (onComplete) onComplete();
    };

    sequence();
  }, []);

  const styles = {
    overlay: {
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'black',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'monospace',
      color: '#00FF00',
      padding: '20px'
    },
    container: {
      width: '100%',
      maxWidth: '600px'
    },
    log: {
      marginBottom: '8px',
      opacity: 0.8
    },
    avatarContainer: {
      marginTop: '40px',
      display: 'flex',
      justifyContent: 'center'
    },
    skipBtn: {
      marginTop: '30px',
      background: 'transparent',
      border: '1px solid #00FF00',
      color: '#00FF00',
      padding: '8px 16px',
      cursor: 'pointer',
      fontFamily: 'monospace',
      opacity: 0.5
    }
  };

  return (
    <div style={styles.overlay}>
      <div style={styles.container}>
        {logs.map((log, i) => (
          <div key={i} style={styles.log}>{log}</div>
        ))}
        {showAvatar && (
            <div style={styles.avatarContainer}>
                <JesterAvatar speaking={speaking} waving={waving} />
            </div>
        )}
        <div style={{textAlign: 'center'}}>
          <button style={styles.skipBtn} onClick={onComplete}>[ OVERRIDE BOOT SEQUENCE ]</button>
        </div>
      </div>
    </div>
  );
};

export default SelfAwarenessTest;

