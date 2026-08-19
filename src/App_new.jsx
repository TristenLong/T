import React, { useState, useEffect, useRef, Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera, Stars } from '@react-three/drei';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Activity, Cpu, Database, Globe, Trash2, Send, Eye, Lock, Waves } from 'lucide-react';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import JesterBrain from './JesterBrain';
import SelfAwarenessTest from './components/SelfAwarenessTest';
import ObservatoryTelemetry from './components/ObservatoryTelemetry';
import ParticleBackground from './components/ParticleBackground';
import ParticleBackground from './components/ParticleBackground';

const AudioVisualizer = ({ isListening, isSpeaking }) => {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationId;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.lineWidth = 2;
      ctx.strokeStyle = isSpeaking ? '#00FF41' : (isListening ? '#FF003C' : '#008F11');
      ctx.beginPath();
      const waveCount = isSpeaking ? 5 : (isListening ? 3 : 1);
      const amp = isSpeaking ? 20 : (isListening ? 10 : 2);
      for (let i = 0; i < canvas.width; i++) {
        const y = canvas.height / 2 + Math.sin(i * 0.05 * waveCount + performance.now() * 0.005) * amp;
        if (i === 0) ctx.moveTo(i, y);
        else ctx.lineTo(i, y);
      }
      ctx.stroke();
      animationId = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animationId);
  }, [isListening, isSpeaking]);
  return <canvas ref={canvasRef} width="300" height="60" style={{ marginTop: '10px', filter: 'drop-shadow(0 0 5px ' + (isSpeaking ? '#00FF41' : '#008F11') + ')' }} />;
};

function App() {
  const [bootSequence, setBootSequence] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isAnomaly, setIsAnomaly] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [vitals, setVitals] = useState({ cpu: 0, ram: 0, status: 'OFFLINE', model: 'N/A', logic_core: 'OFFLINE' });
  const [status, setStatus] = useState('INITIALIZING');
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState('');
  const [diagnostics, setDiagnostics] = useState(null);
  
  const recognitionRef = useRef(null);
  const tts = window.speechSynthesis;
  const autoRestart = useRef(false);

  const theme = { bg: '#000000', main: '#00FF00', sec: '#008F11', err: '#FF003C' };

  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/history?limit=20');
      const data = await res.json();
      if (!data.error) setHistory(data);
    } catch (e) { console.error('HISTORY_SYNC_FAILED'); }
  };

  useEffect(() => {
    const pulse = () => {
      fetch('/api/pulse')
        .then(r => r.json())
        .then(d => { 
          setVitals(d); 
          setStatus('THE_ONE_ONLINE');
        })
        .catch(() => setStatus('SIGNAL_LOST'));
    };
    const int = setInterval(pulse, 3000);
    pulse();
    fetchHistory();

    if ('webkitSpeechRecognition' in window) {
      const rec = new window.webkitSpeechRecognition();
      rec.continuous = true;
      rec.interimResults = true;
      rec.onresult = (e) => {
        let text = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          if (e.results[i].isFinal) handleSend(e.results[i][0].transcript);
          else text += e.results[i][0].transcript;
        }
        setTranscript(text);
      };
      rec.onstart = () => setIsListening(true);
      rec.onend = () => {
        setIsListening(false);
        if (autoRestart.current) setTimeout(() => { try { rec.start(); } catch(err) {} }, 100);
      };
      recognitionRef.current = rec;
    }

    return () => clearInterval(int);
  }, []);

  const speak = (txt) => {
    tts.cancel();
    const ut = new SpeechSynthesisUtterance(txt);
    ut.pitch = 0.8;
    ut.rate = 1.1;
    ut.onstart = () => setIsSpeaking(true);
    ut.onend = () => setIsSpeaking(false);
    tts.speak(ut);
  };

  const handleSend = async (msg) => {
    if (!msg || !msg.trim()) return;
    setStatus('CALCULATING...');
    try {
      const res = await fetch('/api/chat', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ message: msg }) 
      });
      const data = await res.json();
      setResponse(data.response);
      speak(data.response);
      fetchHistory();
      setStatus('THE_ONE_ONLINE');
    } catch (e) {
      setStatus('CORE_ERROR');
      setResponse('ERROR: SYSTEM FAILURE.');
    }
  };

  const runDiagnostics = async () => {
    setDiagnostics('RUNNING_MATRIX_DIAGNOSTICS...');
    let report = [];
    try {
      const res = await fetch('/api/pulse');
      const data = await res.json();
      report.push("[PASS] LOGIC_CORE: " + data.logic_core);
      report.push("[PASS] PRIMARY_MODEL: " + data.model);
      report.push("[PASS] CPU_LOAD: " + data.cpu + "%");
      report.push("[PASS] RAM_USAGE: " + data.ram + "%");
    } catch { report.push('[FAIL] CORE_CONNECTION_SEVERED'); }
    setDiagnostics(report.join('\n'));
    setTimeout(() => setDiagnostics(null), 8000);
  };

  const purge = async () => {
    if(window.confirm('PURGE UNPINNED MEMORY?')) {
      await fetch('/api/reset', { method: 'POST' });
      fetchHistory();
      setResponse('UNPINNED_MEMORY_PURGED');
    }
  };

  const hubActions = [
    { icon: <Eye size={18}/>, label: 'RED PILL', cmd: 'take_pill' },
    { icon: <Lock size={18}/>, label: 'BLUE PILL', cmd: 'take_pill' },
    { icon: <Activity size={18}/>, label: 'REPORT', cmd: 'run system diagnostics' },
    { icon: <Globe size={18}/>, label: 'SEARCH', cmd: 'search the web' },
  ];

  if (bootSequence) {
    return <SelfAwarenessTest onComplete={() => setBootSequence(false)} />;
  }

  return (
    <>
      <ParticleBackground isAnomaly={isAnomaly} />

      <AnimatePresence>
        {diagnostics && (
          <motion.div initial={{opacity:0, scale:0.9}} animate={{opacity:1, scale:1}} exit={{opacity:0}} style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', background: 'rgba(0,15,0,0.95)', border: '1px solid ' + theme.main, padding: '30px', zIndex: 9999, borderRadius: '10px', boxShadow: '0 0 50px ' + theme.sec }}>
            <h2 style={{ color: theme.main, marginBottom: '20px', borderBottom: '1px solid ' + theme.main, fontFamily: 'Orbitron' }}>NEURAL_DIAG_REPORT</h2>
            <pre style={{ fontSize: '0.9rem' }}>{diagnostics}</pre>
            <button onClick={()=>setDiagnostics(null)} style={{ marginTop: '20px', width: '100%', padding: '10px', background: theme.main, color: '#000', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}>ACKNOWLEDGE</button>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="wrap" style={{ position: 'relative', zIndex: 10 }}>
        <header>
          <div className="header-left">
            <div style={{ width: '120px', height: '120px', position: 'relative' }}>
              <Canvas>
                <PerspectiveCamera makeDefault position={[0, 0, 3]} />
                <Stars radius={50} depth={20} count={1000} factor={2} />
                <Suspense fallback={null}>
                  <JesterBrain isSpeaking={isSpeaking} isListening={isListening} isAnomaly={isAnomaly} />
                  <EffectComposer disableNormalPass>
                    <Bloom luminanceThreshold={0.2} mipmapBlur luminanceSmoothing={0.9} intensity={2.5} />
                  </EffectComposer>
                </Suspense>
              </Canvas>
            </div>
            <div>
              <h1 style={{ fontFamily: 'Orbitron', fontWeight: 900, fontSize: '32px', margin: 0, textShadow: '0 0 20px rgba(0,255,136,0.6)' }}>OMNISCIENCE <span style={{ color: '#00ff88' }}>OBSERVATORY</span></h1>
              <div style={{ fontSize: '13px', color: '#6b8f7d', marginTop: '8px', letterSpacing: '0.1em' }}>JESTER V1000 GOD HAND :: QUANTUM / MACRO-STATE / FREQUENCY</div>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px', background: 'rgba(0,0,0,0.4)', padding: '8px 16px', border: '1px solid rgba(0,255,136,0.15)', borderRadius: '4px' }}>
                <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: status === 'THE_ONE_ONLINE' ? '#00ff88' : '#ff3366', boxShadow: status === 'THE_ONE_ONLINE' ? '0 0 12px #00ff88' : '0 0 12px #ff3366', animation: status === 'THE_ONE_ONLINE' ? 'pulse-green 1.5s infinite alternate' : 'none' }}></div>
                <span style={{ fontSize: '12px', letterSpacing: '0.1em', color: '#00ff88', fontFamily: 'Orbitron' }}>{status}</span>
              </div>
              <div style={{ display: 'flex', gap: '15px', fontSize: '11px', color: '#6b8f7d', fontFamily: 'Orbitron' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}><Cpu size={12}/> CPU {vitals.cpu}%</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}><Database size={12}/> RAM {vitals.ram}%</span>
                  <button onClick={runDiagnostics} style={{ background: 'none', border: '1px solid #6b8f7d', color: '#e0f2e9', padding: '2px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '10px' }}>DIAGNOSTICS</button>
                  <button onClick={purge} style={{ color: '#ff3366', background: 'none', border: 'none', cursor: 'pointer' }}><Trash2 size={14}/></button> 
              </div>
          </div>
        </header>

        <div className="grid">
          
          {/* VOICE ASSISTANT ROW */}
          <div className="panel col-12" style={{ display: 'flex', gap: '20px', padding: '20px', alignItems: 'stretch' }}>
            
            {/* Left: Chat log */}
            <div style={{ flex: '0 0 300px', display: 'flex', flexDirection: 'column', borderRight: '1px solid rgba(0,255,136,0.15)', paddingRight: '20px' }}>
                <div className="panel-label"><span>NEURAL_MEMORY</span><Activity size={12} /></div>
                <div style={{ flex: 1, overflowY: 'auto', fontSize: '12px', maxHeight: '180px' }}>
                  {history.map((h, i) => (
                    <div key={h.id || i} style={{ marginBottom: '10px', padding: '8px', background: 'rgba(0,0,0,0.3)', borderRadius: '4px', borderLeft: '3px solid ' + (h.role === 'user' ? theme.sec : theme.main) }}>
                      <div style={{ fontWeight: 'bold', fontSize: '10px', marginBottom: '3px', color: h.role === 'user' ? theme.sec : theme.main }}>{h.role.toUpperCase()}</div>
                      {h.content}
                    </div>
                  ))}
                </div>
            </div>

            {/* Right: AI Response & Inputs */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <AnimatePresence mode='wait'>
                  <motion.div key={response} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={{ textAlign: 'center', maxWidth: '80%', padding: '10px' }}>
                    <div style={{ fontSize: '20px', color: theme.main, textShadow: '0 0 10px ' + theme.sec }}>{response || 'STANDBY_FOR_INPUT'}</div>  
                    {transcript && <div style={{ marginTop: '10px', fontSize: '14px', color: theme.sec, opacity: 0.8 }}>{transcript}</div>}
                  </motion.div>
                </AnimatePresence>

                <AudioVisualizer isListening={isListening} isSpeaking={isSpeaking} />

                <div style={{ display: 'flex', gap: '15px', marginTop: '20px' }}>
                  <button onClick={() => { isListening ? (autoRestart.current = false, recognitionRef.current.stop()) : (autoRestart.current = true, recognitionRef.current.start()); }} style={{ background: isListening ? theme.err : 'rgba(0,0,0,0.8)', border: '1px solid ' + theme.main, color: isListening ? '#fff' : theme.main, padding: '10px 25px', borderRadius: '30px', cursor: 'pointer', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>{isListening ? <><MicOff size={16}/> STOP</> : <><Mic size={16}/> LISTEN</>}</button>

                  <div style={{ display: 'flex', border: '1px solid ' + theme.sec, borderRadius: '30px', overflow: 'hidden', background: 'rgba(0,0,0,0.8)' }}>
                    <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && (handleSend(input), setInput(''))} style={{ background: 'none', border: 'none', color: '#fff', padding: '10px 20px', outline: 'none', width: '250px', fontFamily: 'JetBrains Mono' }} placeholder='ENTER_COMMAND...' />
                    <button onClick={() => { handleSend(input); setInput(''); }} style={{ background: theme.sec, border: 'none', color: '#000', padding: '0 20px', cursor: 'pointer' }}><Send size={16} /></button>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '15px', marginTop: '15px' }}>
                  {hubActions.map((a, i) => (
                    <button key={i} onClick={() => handleSend(a.cmd)} style={{ background: 'rgba(0,10,0,0.5)', border: '1px solid ' + theme.sec + '44', color: theme.sec, padding: '8px 12px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px', fontSize: '10px', fontFamily: 'Orbitron' }} onMouseEnter={e => e.currentTarget.style.borderColor = theme.main} onMouseLeave={e => e.currentTarget.style.borderColor = theme.sec + '44'}>{a.icon}<span>{a.label}</span></button>
                  ))}
                </div>
            </div>

          </div>

          <ObservatoryTelemetry onAnomalyChange={setIsAnomaly} />

        </div>
      </div>
    </>
  );
}

export default App;
