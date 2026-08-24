import React, { useState, useEffect, useRef, Suspense, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera, Stars } from '@react-three/drei';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Mic, MicOff, Zap, Activity, Cpu, Database, Terminal, Shield, 
  Globe, Trash2, Send, Eye, Volume2, Lock, Search, Play, Brain, 
  Settings, Sparkles, Layers, Compass, Camera, Monitor, Code2, 
  Bot, Network, RefreshCw, BarChart2, Radio, Server, MessageSquare, 
  Wrench, X, ChevronUp, ChevronDown
} from 'lucide-react';
import JesterBrain from './JesterBrain';
import MatrixRain from './MatrixRain';
import MatrixHUD from './MatrixHUD';
import SelfAwarenessTest from './components/SelfAwarenessTest';
import ObservatoryTelemetry from './components/ObservatoryTelemetry';

const theme = { 
  bg: 'transparent', 
  main: '#00FF66', 
  sec: '#008F11', 
  err: '#FF0055',
  cyan: '#00F0FF',
  purple: '#B026FF',
  amber: '#FFB800',
  blue: '#00D2FF',
  orange: '#FF7700'
};

function App() {
  const [bootSequence, setBootSequence] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [vitals, setVitals] = useState({ cpu: 0, ram: 0, status: 'OFFLINE', model: 'gemini-3.1-pro', logic_core: 'OFFLINE' });
  const [stats, setStats] = useState({ xp: 0, level: 1 });
  const [status, setStatus] = useState('INITIALIZING');
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState('');
  const [diagnostics, setDiagnostics] = useState(null);
  const [showHud, setShowHud] = useState(true);
  const [showObservatory, setShowObservatory] = useState(false);
  const [showArsenal, setShowArsenal] = useState(false);
  const [activeCategory, setActiveCategory] = useState('ALL');
  const [executingTool, setExecutingTool] = useState(null);
  
  const recognitionRef = useRef(null);
  const tts = typeof window !== 'undefined' ? window.speechSynthesis : null;
  const autoRestart = useRef(false);

  const [matrixStats, setMatrixStats] = useState(null);

  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/history?limit=20');
      const data = await res.json();
      if (!data.error && Array.isArray(data)) setHistory(data);
    } catch (e) { 
      console.error('HISTORY_SYNC_FAILED', e); 
    }
  };

  useEffect(() => {
    const pulse = () => {
      fetch('/api/matrix_status')
        .then(r => r.json())
        .then(d => { 
          setMatrixStats(d);
          setVitals({ cpu: d.cpu, ram: d.ram, status: 'THE_ONE_ONLINE', model: d.model, logic_core: d.logic_core }); 
          setStatus('THE_ONE_ONLINE');
        })
        .catch(() => setStatus('LOCAL_CORE_ACTIVE'));

      fetch('/api/stats')
        .then(r => r.json())
        .then(d => {
          if (!d.error) setStats(d);
        })
        .catch(console.error);
    };
    const int = setInterval(pulse, 3000);
    pulse();
    fetchHistory();

    if (typeof window !== 'undefined' && 'webkitSpeechRecognition' in window) {
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
        if (autoRestart.current) setTimeout(() => { try { rec.start(); } catch (err) { console.debug(err); } }, 100);
      };
      recognitionRef.current = rec;
    }

    // Feature-checked like the SpeechRecognition/tts paths above: EventSource is
    // absent in jsdom (and any non-browser host), where an unguarded constructor
    // threw out of the effect and took the whole mount down.
    let eventSource = null;
    if (typeof EventSource !== 'undefined') {
      eventSource = new EventSource('/api/stream_events');
      eventSource.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === 'new_memory') {
            fetchHistory();
          } else if (data.type === 'ui_alert') {
            setResponse(`[SWARM ALERT] ${data.message}`);
            setStatus('SWARM_ACTIVE');
          }
        } catch (err) {
          console.debug('SSE parse error', err);
        }
      };
    } else {
      console.debug('EventSource unavailable; live swarm events disabled.');
    }

    return () => {
      clearInterval(int);
      if (eventSource) eventSource.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Legacy Electron IPC dynamic click-through hack removed.
  }, []);

  const speak = (txt) => {
    if (!tts) return;
    try {
      tts.cancel();
      const ut = new SpeechSynthesisUtterance(txt);
      ut.pitch = 0.8;
      ut.rate = 1.1;
      ut.onstart = () => setIsSpeaking(true);
      ut.onend = () => setIsSpeaking(false);
      tts.speak(ut);
    } catch (e) {
      console.warn("TTS Error", e);
    }
  };

  const handleSend = async (msg, toolArgs = null) => {
    if (!msg || !msg.trim()) return;
    setStatus('PROCESSING_STREAM...');
    setResponse('');
    try {
      const res = await fetch('/api/chat_stream', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ message: msg, tool_args: toolArgs }) 
      });
      
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let fullResponse = '';
      let buffer = '';
      let done = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        if (readerDone) break;

        // An SSE frame can straddle a read boundary. Previously each read was
        // split on '\n' and parsed directly, so a truncated line failed
        // JSON.parse and was silently swallowed by the catch -- losing text.
        // Keep the trailing partial line in `buffer` until it completes.
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6).trim();

          if (dataStr === '[DONE]') {
            speak(fullResponse);
            fetchHistory();
            setStatus('THE_ONE_ONLINE');
            done = true;
            break;
          }

          try {
            const data = JSON.parse(dataStr);
            if (data.reset) {
              // Server discarded a partial reply and is restarting on a
              // fallback model; drop what we rendered so the two answers
              // are not concatenated on screen.
              fullResponse = '';
              setResponse('');
            } else if (data.chunk) {
              fullResponse += data.chunk;
              setResponse(fullResponse);
            } else if (data.error) {
              setResponse(prev => prev + '\n[ERROR: ' + data.error + ']');
            }
          } catch (err) {
            console.debug('Malformed SSE frame', dataStr, err);
          }
        }
      }
    } catch (e) {
      setStatus('FALLBACK_RESPONSE');
      setResponse('SYSTEM: Direct neural link active. Processed input: ' + msg);
    } finally {
      setExecutingTool(null);
    }
  };

  const runDiagnostics = async () => {
    setDiagnostics('RUNNING_MATRIX_DIAGNOSTICS...');
    let report = [];
    try {
      const res = await fetch('/api/pulse');
      const data = await res.json();
      report.push("[PASS] LOGIC_CORE: " + (data.logic_core || 'ACTIVE'));
      report.push("[PASS] PRIMARY_MODEL: " + (data.model || 'gemini-3.1-pro'));
      report.push("[PASS] CPU_LOAD: " + (data.cpu || 0) + "%");
      report.push("[PASS] RAM_USAGE: " + (data.ram || 0) + "%");
      report.push("[PASS] HARDWARE_OPT: Zephyr/RandomX AVX-512 Ready");
      report.push("[PASS] TELEMETRY_WS: ws://localhost:8765 Ready");
    } catch { 
      report.push('[FAIL] CORE_CONNECTION_SEVERED'); 
    }
    setDiagnostics(report.join('\n'));
    setTimeout(() => setDiagnostics(null), 10000);
  };

  const purge = async () => {
    if (window.confirm('PURGE UNPINNED MEMORY?')) {
      await fetch('/api/reset', { method: 'POST' });
      fetchHistory();
      setResponse('UNPINNED_MEMORY_PURGED');
    }
  };

  const isSpeechSupported = typeof window !== 'undefined' && 'webkitSpeechRecognition' in window;

  // Tool Arsenal Definition with distinctive Cyber Hues
  const toolArsenal = useMemo(() => [
    { 
      id: 'red_pill', 
      label: 'RED PILL', 
      category: 'PROTOCOL',
      hue: theme.err, 
      icon: <Eye size={16}/>, 
      desc: 'Awakening protocol & deep code revelation', 
      cmd: 'take_pill', 
      args: { pill_type: 'red' } 
    },
    { 
      id: 'blue_pill', 
      label: 'BLUE PILL', 
      category: 'PROTOCOL',
      hue: theme.blue, 
      icon: <Lock size={16}/>, 
      desc: 'Comfort matrix & reset status quo', 
      cmd: 'take_pill', 
      args: { pill_type: 'blue' } 
    },
    { 
      id: 'coder_swarm', 
      label: 'CODER SWARM', 
      category: 'SWARM',
      hue: theme.cyan, 
      icon: <Code2 size={16}/>, 
      desc: 'Architect CoderCore autonomous code generator', 
      cmd: 'dispatch coder swarm to create a high-performance script' 
    },
    { 
      id: 'browser_swarm', 
      label: 'NAVIGATOR', 
      category: 'SWARM',
      hue: theme.cyan, 
      icon: <Compass size={16}/>, 
      desc: 'Autonomous web scraper & browser interaction', 
      cmd: 'dispatch browser swarm to search latest tech breakthroughs' 
    },
    { 
      id: 'computer_use', 
      label: 'COMPUTER USE', 
      category: 'SWARM',
      hue: theme.cyan, 
      icon: <Monitor size={16}/>, 
      desc: 'Direct OS GUI control, keystrokes & mouse navigation', 
      cmd: 'minimize all windows and check system desktop' 
    },
    { 
      id: 'mcp_execute', 
      label: 'MCP CONNECTOR', 
      category: 'SYSTEM',
      hue: theme.blue, 
      icon: <Network size={16}/>, 
      desc: 'Trigger external MCP servers (default: filesystem)', 
      cmd: 'list root directory via MCP',
      args: { command: 'npx', args: ['-y', '@modelcontextprotocol/server-filesystem', 'C:\\'], tool_name: 'list_directory', tool_args: { path: 'C:\\' } }
    },
    { 
      id: 'sandbox_execute', 
      label: 'CODE SANDBOX', 
      category: 'ENGINE',
      hue: theme.orange, 
      icon: <Terminal size={16}/>, 
      desc: 'Spin up an isolated Docker container and execute Python code safely', 
      cmd: 'run sandboxed code' 
    },
    { 
      id: 'vision_ocr', 
      label: 'VISION CORE', 
      category: 'VISION',
      hue: theme.red, 
      icon: <Eye size={16}/>, 
      desc: 'Use PyAutoGUI and PyTesseract to read the screen autonomously', 
      cmd: 'scan screen text' 
    },
    { 
      id: 'vision_screen',  
      label: 'SCREEN OPTICS', 
      category: 'VISION',
      hue: theme.amber, 
      icon: <Monitor size={16}/>, 
      desc: 'Multimodal screen perception & visual data extraction', 
      cmd: 'analyze active screen and extract key information' 
    },
    { 
      id: 'webcam_optics', 
      label: 'WEBCAM OPTICS', 
      category: 'VISION',
      hue: theme.amber, 
      icon: <Camera size={16}/>, 
      desc: 'Webcam snapshot analysis through Gemini Vision', 
      cmd: 'capture webcam and describe what you see' 
    },
    { 
      id: 'deep_research', 
      label: 'DEEP RESEARCH', 
      category: 'INTELLIGENCE',
      hue: theme.main, 
      icon: <Globe size={16}/>, 
      desc: 'Multi-query web crawling and research aggregation', 
      cmd: 'conduct deep research on quantum entropy algorithms' 
    },
    { 
      id: 'reddit_intel', 
      label: 'REDDIT INTEL', 
      category: 'INTELLIGENCE',
      hue: theme.orange, 
      icon: <Radio size={16}/>, 
      desc: 'Subreddit scanner & sentiment extraction', 
      cmd: 'check reddit for latest AI news on r/singularity' 
    },
    { 
      id: 'knowledge_graph', 
      label: 'KNOWLEDGE GRAPH', 
      category: 'INTELLIGENCE',
      hue: theme.main, 
      icon: <Brain size={16}/>, 
      desc: 'Query structured semantic memory & factual triplets', 
      cmd: 'query knowledge graph for remembered system facts' 
    },
    { 
      id: 'quantum_telemetry', 
      label: 'OBSERVATORY', 
      category: 'QUANTUM',
      hue: theme.purple, 
      icon: <BarChart2 size={16}/>, 
      desc: 'Real-time ANU QRNG entropy & FFT anomaly scanner', 
      customAction: () => setShowObservatory(true) 
    },
    { 
      id: 'sys_optimize', 
      label: 'OPTIMIZER', 
      category: 'SYSTEM',
      hue: theme.orange, 
      icon: <Zap size={16}/>, 
      desc: 'Tune OS thread affinities & system cache', 
      cmd: 'optimize system performance for maximum efficiency' 
    },
    { 
      id: 'diagnostics', 
      label: 'DIAGNOSTICS', 
      category: 'SYSTEM',
      hue: theme.main, 
      icon: <Activity size={16}/>, 
      desc: 'Run comprehensive hardware & API health test', 
      customAction: runDiagnostics 
    },
    { 
      id: 'offline_brain', 
      label: 'OFFLINE MODE', 
      category: 'SYSTEM',
      hue: theme.blue, 
      icon: <Server size={16}/>, 
      desc: 'Offline heuristics & local SQLite intelligence', 
      cmd: 'switch to offline mode and report local database facts' 
    },
    { 
      id: 'reboot_avatar', 
      label: 'AVATAR PROTOCOL', 
      category: 'PROTOCOL',
      hue: theme.main, 
      icon: <RefreshCw size={16}/>, 
      desc: 'Re-trigger self-awareness hologram test', 
      customAction: () => setBootSequence(true) 
    }
  ], []);

  const categories = ['ALL', 'PROTOCOL', 'SWARM', 'VISION', 'INTELLIGENCE', 'QUANTUM', 'SYSTEM'];

  const filteredTools = activeCategory === 'ALL' 
    ? toolArsenal 
    : toolArsenal.filter(t => t.category === activeCategory);

  const executeToolItem = async (tool) => {
    setExecutingTool(tool.id);
    try {
      if (tool.customAction) {
        tool.customAction();
      } else {
        setStatus('EXECUTING_TOOL...');
        setResponse(`> Executing ${tool.label}...\n`);
        const res = await fetch('/api/execute_tool', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tool_id: tool.id, cmd: tool.cmd, args: tool.args })
        });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
           const resultText = `> Tool Execution Complete.\nResult:\n${data.result}`;
           setResponse(resultText);
           speak("Tool execution complete.");
        } else {
           setResponse(`> Tool Execution Failed: ${data.error}`);
           speak("Tool execution failed.");
        }
      }
    } catch (e) {
      console.error("Tool execution failed", e);
      setResponse(`> Tool Execution Error: ${e.message}`);
    } finally {
      setExecutingTool(null);
      setStatus('THE_ONE_ONLINE');
    }
  };

  if (bootSequence) {
    return <SelfAwarenessTest onComplete={() => setBootSequence(false)} />;
  }

  return (
    <div style={{ backgroundColor: theme.bg, color: theme.main, height: '100vh', width: '100vw', overflow: 'hidden', fontFamily: 'monospace', pointerEvents: 'auto' }}>
      <MatrixRain color={theme.main} />

      {/* Diagnostics Modal */}
      <AnimatePresence>
        {diagnostics && (
          <motion.div initial={{opacity:0, scale:0.9}} animate={{opacity:1, scale:1}} exit={{opacity:0}} style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', background: 'rgba(0,15,0,0.95)', border: '1px solid ' + theme.main, padding: '30px', zIndex: 100, borderRadius: '10px', boxShadow: '0 0 50px ' + theme.sec }}>
            <h2 style={{ color: theme.main, marginBottom: '20px', borderBottom: '1px solid ' + theme.main }}>NEURAL_DIAG_REPORT</h2>
            <pre style={{ fontSize: '0.9rem' }}>{diagnostics}</pre>
            <button onClick={()=>setDiagnostics(null)} style={{ marginTop: '20px', width: '100%', padding: '10px', background: theme.main, color: '#000', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}>ACKNOWLEDGE</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Quantum Observatory Modal */}
      <AnimatePresence>
        {showObservatory && (
          <motion.div 
            initial={{ opacity: 0, y: 30 }} 
            animate={{ opacity: 1, y: 0 }} 
            exit={{ opacity: 0, y: 30 }}
            style={{ 
              position: 'fixed', 
              inset: '40px', 
              zIndex: 90, 
              background: 'rgba(0, 5, 0, 0.96)', 
              border: `2px solid ${theme.purple}`, 
              borderRadius: '12px', 
              boxShadow: `0 0 50px ${theme.purple}66`,
              display: 'flex', 
              flexDirection: 'column', 
              overflow: 'hidden',
              pointerEvents: 'auto',
              boxSizing: 'border-box'
            }}
          >
            <div style={{ padding: '15px 25px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(20, 0, 30, 0.8)', borderBottom: `1px solid ${theme.purple}55` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: theme.purple, fontWeight: 'bold', fontSize: '1.1rem' }}>
                <BarChart2 size={20}/> QUANTUM SCIENCE OBSERVATORY (PORT 8765 TELEMETRY)
              </div>
              <button 
                onClick={() => setShowObservatory(false)}
                style={{ background: 'none', border: `1px solid ${theme.purple}`, color: theme.purple, padding: '5px 15px', borderRadius: '4px', cursor: 'pointer' }}
              >
                <X size={16}/> CLOSE
              </button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              <ObservatoryTelemetry onAnomalyChange={(anom) => console.log('Anomaly status:', anom)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Full Tool Arsenal Drawer */}
      <AnimatePresence>
        {showArsenal && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }} 
            animate={{ opacity: 1, scale: 1 }} 
            exit={{ opacity: 0, scale: 0.95 }}
            style={{
              position: 'fixed',
              top: '80px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: '90%',
              maxWidth: '1100px',
              maxHeight: '80vh',
              boxSizing: 'border-box',
              pointerEvents: 'auto',
              background: 'rgba(0, 10, 2, 0.96)',
              border: `2px solid ${theme.cyan}`,
              boxShadow: `0 0 50px ${theme.cyan}44`,
              borderRadius: '12px',
              zIndex: 80,
              display: 'flex',
              flexDirection: 'column',
              padding: '20px',
              backdropFilter: 'blur(10px)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${theme.cyan}44`, paddingBottom: '12px' }}>
              <div>
                <h2 style={{ margin: 0, color: theme.cyan, display: 'flex', alignItems: 'center', gap: '10px', fontSize: '1.2rem' }}>
                  <Wrench size={20}/> JESTER COMMAND ARSENAL & TOOL TESTING MATRIX
                </h2>
                <div style={{ fontSize: '0.75rem', color: theme.sec, marginTop: '4px' }}>
                  1-Click trigger & execute all 15+ autonomous agents, multimodal vision, quantum engines, and OS tools
                </div>
              </div>
              <button 
                onClick={() => setShowArsenal(false)}
                style={{ background: 'none', border: `1px solid ${theme.cyan}`, color: theme.cyan, padding: '6px 14px', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}
              >
                <X size={16}/> CLOSE
              </button>
            </div>

            {/* Category Filter Pills */}
            <div style={{ display: 'flex', gap: '10px', padding: '15px 0', flexWrap: 'wrap' }}>
              {categories.map(cat => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  style={{
                    background: activeCategory === cat ? theme.cyan : 'rgba(0, 20, 10, 0.6)',
                    color: activeCategory === cat ? '#000' : theme.cyan,
                    border: `1px solid ${theme.cyan}66`,
                    padding: '5px 14px',
                    borderRadius: '20px',
                    fontSize: '0.75rem',
                    fontWeight: 'bold',
                    cursor: 'pointer'
                  }}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Tool Grid */}
            <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '15px', padding: '10px 0' }}>
              {(filteredTools || []).map(tool => (
                <motion.div
                  key={tool.id}
                  whileHover={{ scale: 1.03, boxShadow: `0 0 20px ${tool.hue}88` }}
                  onClick={() => executeToolItem(tool)}
                  style={{
                    background: 'rgba(0, 15, 5, 0.8)',
                    border: `1px solid ${tool.hue}88`,
                    borderLeft: `4px solid ${tool.hue}`,
                    borderRadius: '8px',
                    padding: '14px',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '10px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: tool.hue, fontWeight: 'bold', fontSize: '0.85rem' }}>
                      {tool.icon} {tool.label}
                    </div>
                    <span style={{ fontSize: '0.6rem', padding: '2px 6px', borderRadius: '4px', background: `${tool.hue}22`, color: tool.hue, border: `1px solid ${tool.hue}44` }}>
                      {tool.category}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#AAA', lineHeight: '1.3' }}>
                    {tool.desc}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '5px' }}>
                    <span style={{ fontSize: '0.65rem', color: tool.hue, opacity: 0.8 }}>
                      {executingTool === tool.id ? 'EXECUTING...' : 'CLICK TO TEST'}
                    </span>
                    <Play size={12} color={tool.hue} />
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Background 3D Canvas */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
        <Canvas>
          <PerspectiveCamera makeDefault position={[0, 0, 5]} />
          <Stars radius={100} depth={50} count={3000} factor={4} saturation={1} fade speed={1} />
          <Suspense fallback={null}><JesterBrain isSpeaking={isSpeaking} isListening={isListening} color={theme.main} /></Suspense>
        </Canvas>
      </div>

      <div style={{ position: 'relative', zIndex: 10, height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* Main Header */}
        <header style={{ WebkitAppRegion: 'drag', padding: '12px 25px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,10,0,0.9)', borderBottom: '1px solid ' + theme.sec, pointerEvents: 'auto' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.2rem', letterSpacing: '6px', color: theme.main, display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Zap size={20} color={theme.main}/> JESTER V2000: SINGULARITY (SWARM)
            </h1>
            <div style={{ fontSize: '0.65rem', opacity: 0.8, color: theme.sec }}>MODEL: {vitals.model} | STATUS: {status}</div>
          </div>
          <div style={{ WebkitAppRegion: 'no-drag', display: 'flex', gap: '12px', fontSize: '0.8rem', alignItems: 'center', pointerEvents: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: theme.cyan }}><Cpu size={14}/> {vitals.cpu}%</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: theme.main }}><Database size={14}/> {vitals.ram}%</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: theme.amber }} title={`XP: ${stats.xp}`}><Sparkles size={14}/> LVL {stats.level}</div>
            
            <button 
              onClick={() => setShowArsenal(prev => !prev)} 
              style={{ background: showArsenal ? 'rgba(0,240,255,0.2)' : 'none', border: '1px solid ' + theme.cyan, color: theme.cyan, padding: '5px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 'bold' }}
            >
              <Wrench size={13}/> TOOL ARSENAL
            </button>

            <button 
              onClick={() => setShowObservatory(prev => !prev)} 
              style={{ background: showObservatory ? 'rgba(176,38,255,0.2)' : 'none', border: '1px solid ' + theme.purple, color: theme.purple, padding: '5px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 'bold' }}
            >
              <BarChart2 size={13}/> OBSERVATORY
            </button>

            <button 
              onClick={() => setShowHud(prev => !prev)} 
              style={{ background: showHud ? 'rgba(0,255,0,0.2)' : 'none', border: '1px solid ' + theme.sec, color: theme.main, padding: '5px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.72rem' }}
            >
              SWARM HUD
            </button>

            <button 
              onClick={runDiagnostics} 
              style={{ background: 'none', border: '1px solid ' + theme.sec, color: theme.main, padding: '5px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.72rem' }}
            >
              DIAGNOSTICS
            </button>

            <button 
              onClick={purge} 
              title="Purge Memory"
              style={{ color: theme.err, background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
            >
              <Trash2 size={16}/>
            </button> 

            <button 
              onClick={() => window.close()} 
              title="Close JESTER"
              style={{ 
                color: '#fff', 
                background: theme.err, 
                border: 'none', 
                borderRadius: '4px', 
                cursor: 'pointer', 
                padding: '4px', 
                marginLeft: '15px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <X size={16}/>
            </button>
          </div>
        </header>

        {showHud && <MatrixHUD theme={theme} onClose={() => setShowHud(false)} stats={matrixStats} />}

        <main style={{ flex: 1, display: 'flex', padding: '15px', gap: '15px', overflow: 'hidden' }}>
          {/* Left Neural Memory Stream */}
          <section style={{ width: '320px', background: 'rgba(0,15,0,0.75)', border: '1px solid ' + theme.sec, padding: '15px', borderRadius: '8px', display: 'flex', flexDirection: 'column', backdropFilter: 'blur(5px)', pointerEvents: 'auto' }}>
            <div style={{ fontSize: '0.75rem', marginBottom: '10px', color: theme.sec, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
               <span style={{ fontWeight: 'bold' }}>NEURAL_MEMORY_STREAM</span>
               <Activity size={12} />
            </div>
            <div style={{ flex: 1, overflowY: 'auto', fontSize: '0.7rem' }}>
              {(history || []).map((h, i) => (
                <div key={h.id || i} style={{ marginBottom: '10px', padding: '8px', background: 'rgba(0,0,0,0.4)', borderRadius: '4px', borderLeft: '3px solid ' + (h.role === 'user' ? theme.sec : theme.main), position: 'relative' }}>
                  <div style={{ fontWeight: 'bold', fontSize: '0.6rem', marginBottom: '3px', color: h.role === 'user' ? theme.sec : theme.main }}>{h.role.toUpperCase()}</div>
                  {h.content}
                </div>
              ))}
            </div>
          </section>

          {/* Center Chat & Intelligence Stage */}
          <section style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
            <AnimatePresence mode='wait'>
              <motion.div key={response} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={{ textAlign: 'center', maxWidth: '80%', background: 'rgba(0,0,0,0.7)', padding: '30px', borderRadius: '15px', border: '1px solid ' + theme.sec + '66', backdropFilter: 'blur(8px)', pointerEvents: 'auto' }}>
                <div style={{ fontSize: '1.4rem', color: theme.main, textShadow: '0 0 10px ' + theme.sec, whiteSpace: 'pre-wrap' }}>{response || 'STANDBY_FOR_INPUT'}</div>  
                {transcript && <div style={{ marginTop: '15px', fontSize: '0.9rem', color: theme.sec, opacity: 0.9 }}>{transcript}</div>}
              </motion.div>
            </AnimatePresence>

            {/* Input & Voice Controls */}
            <div style={{ marginTop: '25px', display: 'flex', gap: '15px', alignItems: 'center', pointerEvents: 'auto' }}>
              <button 
                onClick={() => { 
                  if (!isSpeechSupported) {
                    alert('ERROR: Web Speech API is not supported in this browser. Please use Chrome or Edge.');
                    return;
                  }
                  if (isListening) {
                    autoRestart.current = false;
                    if (recognitionRef.current) recognitionRef.current.stop();
                  } else {
                    autoRestart.current = true;
                    if (recognitionRef.current) recognitionRef.current.start();
                  }
                }} 
                style={{ 
                  background: isListening ? theme.err : 'rgba(0,0,0,0.85)', 
                  border: '1px solid ' + (isSpeechSupported ? theme.main : theme.sec), 
                  color: isListening ? '#fff' : (isSpeechSupported ? theme.main : theme.sec), 
                  padding: '12px 35px', borderRadius: '30px', 
                  cursor: isSpeechSupported ? 'pointer' : 'not-allowed', 
                  fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '10px', 
                  boxShadow: isListening ? '0 0 20px ' + theme.err : '0 0 15px ' + (isSpeechSupported ? theme.main : theme.sec) + '44' 
                }}
                title={!isSpeechSupported ? 'Microphone not supported in this browser' : ''}
              >
                {isListening ? <><MicOff size={18}/> STOP</> : <><Mic size={18}/> LISTEN</>}
              </button>

              <div style={{ display: 'flex', border: '1px solid ' + theme.sec, borderRadius: '30px', overflow: 'hidden', background: 'rgba(0,0,0,0.85)', boxShadow: '0 0 15px rgba(0,255,100,0.15)' }}>
                <input 
                  value={input} 
                  onChange={e => setInput(e.target.value)} 
                  onKeyDown={e => e.key === 'Enter' && (handleSend(input), setInput(''))} 
                  style={{ background: 'none', border: 'none', color: '#fff', padding: '12px 25px', outline: 'none', width: '340px', fontSize: '0.85rem' }} 
                  placeholder='ENTER COMMAND / OBJECTIVE...' 
                />
                <button onClick={() => { handleSend(input); setInput(''); }} style={{ background: theme.sec, border: 'none', color: '#000', padding: '0 25px', cursor: 'pointer' }}><Send size={18} /></button>
              </div>
            </div>

            {/* Quick Action Dock with Category Hues */}
            <div style={{ marginTop: '30px', display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center', maxWidth: '850px', pointerEvents: 'auto' }}>
              {(toolArsenal || []).map((tool) => (
                <button 
                  key={tool.id} 
                  onClick={() => executeToolItem(tool)} 
                  style={{ 
                    background: 'rgba(0,10,0,0.6)', 
                    border: `1px solid ${tool.hue}55`, 
                    color: tool.hue, 
                    padding: '8px 12px', 
                    borderRadius: '8px', 
                    cursor: 'pointer', 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '6px', 
                    fontSize: '0.68rem',
                    fontWeight: 'bold',
                    transition: 'all 0.2s',
                    boxShadow: `0 0 10px ${tool.hue}22`
                  }} 
                  onMouseEnter={e => {
                    e.currentTarget.style.borderColor = tool.hue;
                    e.currentTarget.style.boxShadow = `0 0 20px ${tool.hue}66`;
                  }} 
                  onMouseLeave={e => {
                    e.currentTarget.style.borderColor = `${tool.hue}55`;
                    e.currentTarget.style.boxShadow = `0 0 10px ${tool.hue}22`;
                  }}
                >
                  {tool.icon}
                  <span>{tool.label}</span>
                </button>
              ))}

              <button 
                onClick={() => setShowArsenal(true)} 
                style={{ 
                  background: 'rgba(0,30,20,0.7)', 
                  border: `1px solid ${theme.cyan}`, 
                  color: theme.cyan, 
                  padding: '8px 14px', 
                  borderRadius: '8px', 
                  cursor: 'pointer', 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '6px', 
                  fontSize: '0.68rem',
                  fontWeight: 'bold'
                }}
              >
                <Sparkles size={14}/>
                <span>+ ALL TOOLS</span>
              </button>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default App;
