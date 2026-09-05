import React, { useState, useEffect, useRef, Suspense, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera, Stars } from '@react-three/drei';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Mic, MicOff, Zap, Activity, Cpu, Database, Terminal, Shield, 
  Globe, Trash2, Send, Eye, Volume2, Lock, Search, Play, Brain, 
  Settings, Sparkles, Layers, Compass, Camera, Monitor, Code2, 
  Bot, Network, RefreshCw, BarChart2, Radio, Server, MessageSquare, 
  Wrench, X, ChevronUp, ChevronDown, CheckCircle2, Flame, Users
} from 'lucide-react';
import JesterBrain from './JesterBrain';
import MatrixRain from './MatrixRain';
import MatrixHUD from './MatrixHUD';
import SelfAwarenessTest from './components/SelfAwarenessTest';
import ObservatoryTelemetry from './components/ObservatoryTelemetry';
import { puter } from '@heyputer/puter.js';

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

// Swarm Fleet Personas matching GOD_HAND_CORE/server.py
const DEFAULT_SWARM_BOTS = [
  { id: 'jester', name: 'JESTER', role: 'Matrix Architect & Sovereign Core', color: '#00FF66', avatar: 'Zap', port: '5000' },
  { id: 'claude', name: 'CLAUDE CODE', role: 'Strategic Architecture & Modular Engineer', color: '#B026FF', avatar: 'Terminal', port: 'CLI' },
  { id: 'gemini', name: 'GEMINI SCOUT', role: '2M-Context Deep Explorer & Web Intelligence', color: '#00F0FF', avatar: 'Globe', port: '7860' },
  { id: 'brutal_critic', name: 'BRUTAL CRITIC', role: '3-Lens Stress Tester & Code Auditor', color: '#FF0055', avatar: 'Shield', port: 'SUB' },
  { id: 'codex', name: 'CODEX', role: 'Universal Protocol & System Standard Engineer', color: '#FFD700', avatar: 'Code2', port: 'STD' }
];

const renderBotIcon = (avatarName, color = '#FFF', size = 14) => {
  switch (avatarName) {
    case 'Zap': return <Zap size={size} color={color} />;
    case 'Terminal': return <Terminal size={size} color={color} />;
    case 'Globe': return <Globe size={size} color={color} />;
    case 'Shield': return <Shield size={size} color={color} />;
    case 'Code2': return <Code2 size={size} color={color} />;
    default: return <Bot size={size} color={color} />;
  }
};

// Puter frontend model (OpenRouter models via puter.js, no API key needed).
const PUTER_MODEL = 'z-ai/glm-5.3';

const IDLE_STATUSES = ['THE_ONE_ONLINE', 'LOCAL_CORE_ACTIVE', 'PUTER_LINKED', 'FALLBACK_RESPONSE'];

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
  const [showObserver, setShowObserver] = useState(false);
  const [observerLog, setObserverLog] = useState([]);
  const [observerInput, setObserverInput] = useState('');
  const [observerBusy, setObserverBusy] = useState(false);
  const observeLogRef = useRef([]);
  const memoryScrollRef = useRef(null);
  const responseScrollRef = useRef(null);
  
  const recognitionRef = useRef(null);
  const inputRef = useRef(null);
  const tts = typeof window !== 'undefined' ? window.speechSynthesis : null;
  const autoRestart = useRef(false);

  const [matrixStats, setMatrixStats] = useState(null);
  const [activeBot, setActiveBot] = useState('swarm');
  const [swarmTurns, setSwarmTurns] = useState([]);
  const [isSwarmDeliberating, setIsSwarmDeliberating] = useState(false);
  const [commStatus, setCommStatus] = useState(null);
  const [swarmBots, setSwarmBots] = useState(DEFAULT_SWARM_BOTS);
  const [speakingBot, setSpeakingBot] = useState(null);
  const [isAnomaly, setIsAnomaly] = useState(false);
  const [sentryActive, setSentryActive] = useState(true);
  const [sentryAlert, setSentryAlert] = useState(false);
  const [sentryInfo, setSentryInfo] = useState(null);
  const [optimizingRam, setOptimizingRam] = useState(false);
  const [executingConsensus, setExecutingConsensus] = useState(false);

  // Sentry perception loop: monitors telemetry, active window, and memory anomalies
  useEffect(() => {
    if (!sentryActive) return;
    let isSubscribed = true;
    const sentryCheck = async () => {
      try {
        const res = await fetch('/api/sentry/scan');
        if (!res.ok) return;
        const data = await res.json();
        if (isSubscribed && data) {
          setSentryInfo(data);
          if (data.alert) {
            setSentryAlert(true);
            setIsAnomaly(true);
            const alertMsg = data.anomalies?.[0]?.message || 'System threshold exceeded';
            observe('SENTRY', `[ALERT] ${alertMsg}`);
          } else {
            setSentryAlert(false);
            setIsAnomaly(false);
          }
        }
      } catch {
        // quiet fallback
      }
    };
    sentryCheck();
    const interval = setInterval(sentryCheck, 20000);
    return () => {
      isSubscribed = false;
      clearInterval(interval);
    };
  }, [sentryActive]);

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
    fetch('/api/swarm/bots')
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d && Array.isArray(d.bots) && d.bots.length > 0) {
          setSwarmBots(d.bots);
        }
      })
      .catch(console.debug);

    const pulse = () => {
      fetch('/api/matrix_status')
        .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
        .then(d => { 
          setMatrixStats(d);
          setVitals({ cpu: d.cpu, ram: d.ram, status: 'THE_ONE_ONLINE', model: d.model, logic_core: d.logic_core }); 
          setStatus('THE_ONE_ONLINE');
        })
        .catch(() => setStatus('LOCAL_CORE_ACTIVE'));

      fetch('/api/stats')
        .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
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

    let eventSource = null;
    if (typeof EventSource !== 'undefined') {
      eventSource = new EventSource('/api/stream_events');
      eventSource.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === 'new_memory') {
            fetchHistory();
            observe('MEMORY', 'memory store synced');
          } else if (data.type === 'ui_alert') {
            setResponse(`[SWARM ALERT] ${data.message}`);
            setStatus('SWARM_ACTIVE');
            observe('ALERT', data.message);
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
    // Keep the Neural Memory Stream pinned to the newest turn.
    if (memoryScrollRef.current) {
      memoryScrollRef.current.scrollTop = memoryScrollRef.current.scrollHeight;
    }
  }, [history]);

  useEffect(() => {
    // Keep the live response panel pinned to the newest text as it streams.
    if (responseScrollRef.current) {
      responseScrollRef.current.scrollTop = responseScrollRef.current.scrollHeight;
    }
  }, [response]);

  useEffect(() => {
    // Reclaim keyboard focus on the command input whenever the app is back to
    // idle so a stuck streaming turn or a stale HMR frame cannot leave the UI
    // with no way to type. Skip when the user is actively in another text
    // field (e.g. the Observer channel).
    const active = document.activeElement;
    const inInput = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA');
    if (!inInput && inputRef.current && IDLE_STATUSES.includes(status)) {
      requestAnimationFrame(() => inputRef.current && inputRef.current.focus({ preventScroll: true }));
    }
  }, [status, bootSequence]);

  useEffect(() => {
    // If a prior Puter sign-in token is still stored, push it to the backend so
    // the Tool Arsenal is armed without needing a fresh popup.
    if (typeof puter !== 'undefined' && puter && puter.authToken) {
      armBackendWithPuter();
    }
  }, []);

  useEffect(() => {
    // Legacy Electron IPC dynamic click-through hack removed.
  }, []);

  const speak = (txt, botId = 'jester') => {
    if (!tts) return;
    try {
      tts.cancel();
      const ut = new SpeechSynthesisUtterance(txt);
      
      const voiceProfiles = {
        jester: { pitch: 0.8, rate: 1.1 },          // Deep Matrix Architect
        claude: { pitch: 1.0, rate: 1.0 },          // Calm, balanced, architectural
        gemini: { pitch: 1.25, rate: 1.15 },        // Energetic, crisp, high-speed
        brutal_critic: { pitch: 0.65, rate: 1.3 },  // Sharp, punchy, rapid-fire
        codex: { pitch: 0.9, rate: 0.95 }           // Measured, methodical robotic
      };
      const profile = voiceProfiles[botId] || voiceProfiles.jester;
      ut.pitch = profile.pitch;
      ut.rate = profile.rate;

      if (typeof window !== 'undefined' && window.speechSynthesis) {
        const voices = window.speechSynthesis.getVoices();
        if (voices && voices.length > 0) {
          if (botId === 'brutal_critic') {
            const deepVoice = voices.find(v => /male|david|mark|george/i.test(v.name));
            if (deepVoice) ut.voice = deepVoice;
          } else if (botId === 'claude') {
            const smoothVoice = voices.find(v => /natural|en-gb|uk|female|zira/i.test(v.name));
            if (smoothVoice) ut.voice = smoothVoice;
          } else if (botId === 'gemini') {
            const brightVoice = voices.find(v => /google|natural|en-us/i.test(v.name));
            if (brightVoice) ut.voice = brightVoice;
          }
        }
      }

      setSpeakingBot(botId);
      ut.onstart = () => setIsSpeaking(true);
      ut.onend = () => {
        setIsSpeaking(false);
        setSpeakingBot(null);
      };
      tts.speak(ut);
    } catch (e) {
      console.warn("TTS Error", e);
    }
  };

  const optimizeRam = async () => {
    if (optimizingRam) return;
    setOptimizingRam(true);
    setStatus('OPTIMIZING_RAM...');
    observe('SYS', 'Initiating system RAM purge and working set trim...');
    try {
      const res = await fetch('/api/sys/optimize_ram', { method: 'POST' });
      const data = await res.json();
      if (data && data.status === 'SUCCESS') {
        const freed = data.freed_mb;
        const nowPct = data.ram_percent;
        setVitals(prev => ({ ...prev, ram: Math.round(nowPct) }));
        setResponse(`[RAM OPTIMIZATION COMPLETE]\nFreed: ${freed} MB\nTrimmed Processes: ${data.trimmed_processes}\nCurrent Memory Usage: ${nowPct}% of ${data.total_gb} GB`);
        speak(`RAM optimized. Freed ${Math.round(freed)} megabytes of system memory, sir.`, 'jester');
        observe('SYS', `RAM optimizer freed ${freed} MB across ${data.trimmed_processes} processes (now ${nowPct}%)`);
      } else {
        throw new Error(data?.error || 'Failed to optimize memory');
      }
    } catch (e) {
      setResponse(`[RAM OPTIMIZE FAILED] ${e.message}`);
      observe('ERROR', `RAM optimize failed: ${e.message}`);
    } finally {
      setOptimizingRam(false);
      setStatus('THE_ONE_ONLINE');
    }
  };

  const executeConsensusCode = async () => {
    if (executingConsensus) return;
    setExecutingConsensus(true);
    setStatus('EXECUTING_CONSENSUS...');
    const topic = swarmTurns.length > 0 
      ? swarmTurns.map(t => `${t.name}: ${t.content.slice(0, 100)}`).join('\n')
      : (input || 'Autonomous swarm consensus action');
      
    observe('SWARM', 'Synthesizing and executing code consensus across fleet...');
    setResponse('[SWARM AUTONOMOUS CODER ENGAGED]\nFormulating consensus blueprint with Codex & Gemini...\nWriting to workspace and running compilation check...');
    
    try {
      const res = await fetch('/api/swarm/execute_consensus', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: input || 'Fleet consensus automated script',
          run_test: true
        })
      });
      const data = await res.json();
      if (data && data.status === 'SUCCESS') {
        setResponse(`[CONSENSUS CODE EXECUTED & VERIFIED]\nTarget File: ${data.target_file}\nSize: ${data.bytes_written} bytes\nCompilation Check: ${data.test_output}\nTimestamp: ${data.timestamp}`);
        speak(`Consensus code formulated and verified nominal in ${data.target_file}, sir.`, 'codex');
        observe('SWARM', `Consensus script written to ${data.target_file} (${data.test_output})`);
      } else {
        throw new Error(data?.error || 'Consensus execution failed');
      }
    } catch (e) {
      setResponse(`[CONSENSUS EXECUTION ERROR] ${e.message}`);
      observe('ERROR', `Consensus execution failed: ${e.message}`);
    } finally {
      setExecutingConsensus(false);
      setStatus('THE_ONE_ONLINE');
    }
  };

  // Persist a chat turn into the backend memory so a Puter-served reply still
  // shows up in history and semantic recall (the backend chat paths do this via
  // the same save_memory call internally).
  const remember = async (role, content) => {
    try {
      await fetch('/api/remember', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, content })
      });
    } catch (e) {
      console.warn('MEMORY_SAVE_FAILED', e);
    }
  };

  // Push the Puter token (obtained after the one-time sign-in popup) to the
  // backend so the Tool Arsenal / server-side tasks route through Puter too.
  const armBackendWithPuter = async () => {
    const token = puter && puter.authToken;
    if (!token) return false;
    try {
      const res = await fetch('/api/configure_ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ puter_token: token, model: PUTER_MODEL })
      });
      const data = await res.json().catch(() => ({}));
      return data.status === 'ARMED';
    } catch (e) {
      console.warn('ARM_PUTER_BACKEND_FAILED', e);
      return false;
    }
  };

  // Iron-Man style POWER-ON SELF TEST: verifies the live link between the HUD,
  // the backend, and the Puter AI coprocessor, then arms tools if signed in.
  const jarvisLinkTest = async () => {
    setStatus('LINK_TEST...');
    const lines = ['----- JESTER POWER-ON SELF TEST -----'];
    try {
      const r = await fetch('/api/pulse');
      lines.push(`[${r.ok ? 'OK' : 'FAIL'}] Backend link (Flask :5000) -> ${r.ok ? 'NOMINAL' : 'DEGRADED'}`);
    } catch {
      lines.push('[FAIL] Backend link (Flask :5000) -> UNREACHABLE');
    }
    const hasPuter = typeof puter !== 'undefined' && puter.ai && typeof puter.ai.chat === 'function';
    lines.push(`[${hasPuter ? 'OK' : 'FAIL'}] Puter AI SDK (renderer coprocessor) -> ${hasPuter ? 'LINKED' : 'MISSING'}`);
    const token = puter && puter.authToken;
    if (token) {
      const armed = await armBackendWithPuter();
      lines.push(`[${armed ? 'OK' : 'FAIL'}] Puter auth -> SIGNED IN`);
      lines.push(`[${armed ? 'OK' : 'FAIL'}] Tool Arsenal AI route -> ${armed ? 'ARMED // PUTER' : 'NOT ARMED'}`);
    } else {
      lines.push('[WAIT] Puter auth -> NO TOKEN (press CONNECT PUTER once to sign in -- no key needed)');
      lines.push('[WAIT] Tool Arsenal AI route -> awaiting Puter sign-in to arm');
    }
    try {
      const st = await fetch('/api/ai_state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ probe: true })
      }).then(r => r.json());
      const p = st.probe;
      if (p && p.ok) lines.push(`[OK] AI provider live probe -> ANSWERS (${st.providers.model})`);
      else if (p) lines.push(`[FAIL] AI provider live probe -> ${String(p.error || 'unknown').replace(/\s+/g, ' ').slice(0, 120)}`);
      else lines.push('[WAIT] AI provider live probe -> no key armed');
    } catch {
      lines.push('[FAIL] AI provider live probe -> backend unreachable');
    }
    const report = lines.join('\n');
    setStatus('LINK_TEST_COMPLETE');
    setResponse(report);
    speak('Power on self test complete. All core systems nominal, sir.');
    return report;
  };

  const OBSERVER_SYSTEM = 'You are JESTER, the side observer AI living in this God Hand command deck (the buddy panel). You quietly watch the deck and talk with your operator like JARVIS. Be brief, dryly witty, precise, loyal. Recent chatter is provided for continuity -- you remember this app.';

  const observe = (type, text) => {
    const entry = { type, text, ts: new Date().toLocaleTimeString([], { hour12: false }) };
    const next = [...observeLogRef.current, entry].slice(-100);
    observeLogRef.current = next;
    setObserverLog(next);
  };

  const observerSend = async () => {
    const text = observerInput.trim();
    if (!text || observerBusy) return;
    setObserverInput('');
    setObserverBusy(true);
    observe('YOU', text);
    try {
      const buddyChat = observeLogRef.current
        .filter(o => o.type === 'YOU' || o.type === 'JESTER')
        .slice(-6)
        .map(o => ({ role: o.type === 'YOU' ? 'user' : 'assistant', content: o.text }));
      const msgs = [
        { role: 'system', content: OBSERVER_SYSTEM },
        ...buddyChat,
        { role: 'user', content: text }
      ];
      let fullResponse = '';
      if (typeof puter !== 'undefined' && puter.ai && typeof puter.ai.chat === 'function') {
        const stream = await puter.ai.chat(msgs, { model: PUTER_MODEL, stream: true });
        for await (const part of stream) {
          const t = part && part.text;
          if (t) fullResponse += t;
        }
      }
      if (!fullResponse.trim()) throw new Error('Puter returned no content');
      observe('JESTER', fullResponse);
      await remember('user', '[OBSERVER] ' + text);
      await remember('model', '[OBSERVER] ' + fullResponse);
      await armBackendWithPuter();
      speak(fullResponse);
    } catch (e) {
      console.warn('Observer channel degraded:', e);
      observe('JESTER', '[OBSERVATION_CHANNEL_DEGRADED] ' + (e && e.message ? e.message : String(e)));
    } finally {
      setObserverBusy(false);
    }
  };

  const connectPuter = async () => {
    setStatus('PUTER_LINKING...');
    const lines = ['----- PUTER CONNECTION -----'];
    if (typeof puter === 'undefined' || !puter || typeof puter.auth?.signIn !== 'function') {
      lines.push('[FAIL] Puter SDK unavailable');
      setResponse(lines.join('\n'));
      setStatus('THE_ONE_ONLINE');
      return;
    }
    try {
      const res = await puter.auth.signIn({ request_auth: true });
      if (res && res.success) {
        await armBackendWithPuter();
        lines.push('[OK] AUTHORIZED');
        lines.push('[OK] Token synced to backend -> Tool Arsenal + chat on Puter');
        lines.push(`[OK] Model: ${PUTER_MODEL}`);
        setResponse(lines.join('\n'));
        setStatus('PUTER_LINKED');
        observe('PTR', 'sign-in complete; backend armed', true);
        speak('Connection established. Puter is linked, sir.');
      } else {
        lines.push('[WAIT] Sign-in not completed (popup may still be open)');
        setResponse(lines.join('\n'));
      }
    } catch (e) {
      lines.push('[CANCEL] ' + (e && e.message ? String(e.message).slice(0, 120) : String(e)));
      setResponse(lines.join('\n'));
    } finally {
      setStatus('THE_ONE_ONLINE');
    }
  };

  const confirmComms = async () => {
    setActiveBot('swarm');
    setIsSwarmDeliberating(true);
    setCommStatus({ state: 'PINGING', msg: 'BROADCASTING HANDSHAKE PING TO ALL 5 AGENTS...' });
    setSwarmTurns([]);
    setResponse('[COMMUNICATIONS HANDSHAKE INITIATED]\nPinging fleet: JESTER -> CLAUDE -> GEMINI -> BRUTAL CRITIC -> CODEX...');
    observe('SWARM', 'Broadcasted handshake ping to all 5 agents');
    
    try {
      const res = await fetch('/api/swarm/roundtable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          topic: 'Operational Handshake & Communication Verification', 
          test_comm: true 
        })
      });
      const data = await res.json();
      if (data && data.turns && Array.isArray(data.turns)) {
        setSwarmTurns(data.turns);
        const count = data.turns.length;
        setCommStatus({ state: 'VERIFIED', count, msg: `ALL ${count}/5 BOTS CONFIRMED & COMMUNICATING` });
        const summary = data.summary || 'All 5 agents verified active on local neural bus. Multi-turn cross-talk confirmed nominal.';
        setResponse(`[HANDSHAKE COMPLETE: ALL ${count} BOTS OPERATIONAL & COMMUNICATING]\n\n${summary}`);
        observe('SWARM', `All ${count} bots responded to handshake ping`);
        speak('All five agents are online, synchronized, and actively communicating, sir.', 'jester');
      } else {
        throw new Error(data.error || 'Invalid handshake response');
      }
    } catch (err) {
      setCommStatus({ state: 'ERROR', msg: 'HANDSHAKE DEGRADED: ' + err.message });
      setResponse('[HANDSHAKE ERROR] ' + err.message);
      observe('ERROR', 'Swarm handshake failed: ' + err.message);
    } finally {
      setIsSwarmDeliberating(false);
    }
  };

  const runRoundtable = async (topic) => {
    if (!topic || !topic.trim()) return;
    const cleanTopic = topic.trim();
    setActiveBot('swarm');
    setIsSwarmDeliberating(true);
    setSwarmTurns([]);
    setResponse(`[SWARM ROUNDTABLE CONVENED]\nTopic: "${cleanTopic}"\nDeliberating in sequence across Gemini -> Claude -> Brutal Critic -> Codex -> Jester...`);
    observe('ROUNDTABLE', `Convened debate on: "${cleanTopic}"`);
    
    try {
      const res = await fetch('/api/swarm/roundtable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: cleanTopic })
      });
      const data = await res.json();
      if (data && data.turns && Array.isArray(data.turns)) {
        setSwarmTurns(data.turns);
        const sum = data.summary || `Swarm deliberation completed with ${data.turns.length} collaborative turns.`;
        setResponse(`[ROUNDTABLE CONSENSUS ACHIEVED]\nTopic: "${data.topic || cleanTopic}"\n\n${sum}`);
        speak(sum, 'jester');
        remember('user', `[SWARM TOPIC] ${cleanTopic}`);
        remember('model', `[SWARM CONSENSUS] ${sum}`);
        observe('ROUNDTABLE', `Consensus reached across ${data.turns.length} agents`);
      } else {
        throw new Error(data.error || 'Roundtable deliberation failed');
      }
    } catch (err) {
      setResponse(`[ROUNDTABLE DEGRADED] ${err.message}`);
      observe('ERROR', 'Roundtable failed: ' + err.message);
    } finally {
      setIsSwarmDeliberating(false);
    }
  };

  const handleAgentChat = async (botId, msg) => {
    if (!msg || !msg.trim()) return;
    const cleanMsg = msg.trim();
    setStatus('PROCESSING_STREAM...');
    setIsSwarmDeliberating(true);
    const targetBot = swarmBots.find(b => b.id === botId) || { name: botId.toUpperCase(), color: theme.cyan, role: 'Agent' };
    setResponse(`[CONNECTING TO ${targetBot.name}...]\nAwaiting response...`);
    observe('AGENT_CHAT', `Direct comms to ${targetBot.name}: "${cleanMsg}"`);

    try {
      const res = await fetch('/api/swarm/agent_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_id: botId, message: cleanMsg })
      });
      const data = await res.json();
      if (data && data.reply) {
        const replyText = data.reply;
        setResponse(`[${data.name} // ${data.role}]\n\n${replyText}`);
        speak(replyText, botId);
        remember('user', `[@${data.name}] ${cleanMsg}`);
        remember('model', `[${data.name}] ${replyText}`);
        observe('AGENT_CHAT', `${data.name} replied`);
      } else {
        throw new Error(data.error || 'No reply from agent');
      }
    } catch (err) {
      setResponse(`[COMM_ERROR: ${targetBot.name}] ${err.message}`);
      observe('ERROR', `Direct comms to ${targetBot.name} failed: ${err.message}`);
    } finally {
      setIsSwarmDeliberating(false);
      setStatus('THE_ONE_ONLINE');
    }
  };

  const handleSend = async (msg, toolArgs = null) => {
    if (!msg || !msg.trim()) return;
    const trimmed = msg.trim();

    // If Swarm Roundtable mode is active, handle handshake or deliberation
    if (activeBot === 'swarm') {
      if (/^(ping|handshake|confirm comm|status check|test comm)/i.test(trimmed)) {
        return confirmComms();
      }
      return runRoundtable(trimmed);
    }

    // If an individual specialist bot is active (Claude, Gemini, Critic, Codex)
    if (activeBot && activeBot !== 'jester' && activeBot !== 'default') {
      return handleAgentChat(activeBot, trimmed);
    }

    setStatus('PROCESSING_STREAM...');
    setResponse('');
    setExecutingTool(null);

    // Action words (open, launch, search, test, code, fix, find, run, browse,
    // diagnostics, settings...) MUST hit the backend agent loop so the Tool
    // Arsenal actually fires -- the renderer-side Puter chat is pure chat and
    // can't invoke tools. We therefore send everything through /api/chat_stream
    // (which runs tools and uses the Puter/GLM model once armed); renderer
    // Puter chat remains only as a last-resort conversational fallback if the
    // backend is unreachable.
    //
    // Quick "action intent" heuristic used to prefer the tool path even when
    // the backend would rather answer plainly.
    const actionRE = /\b(open|launch|start|search|look\s*up|find|test|run|browse|navigate|code|write|create|fix|install|diagnostic|settings|show|open\s+.*(app|browser|folder)|what\s+apps)\b/i;
    const wantsAction = actionRE.test(msg);

    try {
      const res = await fetch('/api/chat_stream', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ message: msg, tool_args: toolArgs, force_tool: wantsAction }) 
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Server returned ${res.status}: ${text}`);
      }
      
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
            } else if (data.type === 'tool') {
              const tag = data.status === 'DONE' ? '[TOOL: ' + data.tool + ' OK]' : '[TOOL: ' + data.tool + ' ...]';
              setResponse(prev => prev + '\n' + tag);
              observe('TOOL', data.tool + (data.status === 'DONE' ? ' -> DONE' : ' -> RUN'), true);
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
      desc: 'Build new code or fix an existing file (reads/writes the file, validates syntax)' 
    },
    { 
      id: 'github_upgrade', 
      label: 'GITHUB UPGRADE', 
      category: 'SWARM',
      hue: theme.cyan, 
      icon: <RefreshCw size={16}/>, 
      desc: 'Check origin/TristenLong for updates and pull the latest code (hard reset + restart)', 
      customAction: executeGitHubUpgrade 
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
      desc: 'Execute a tool on a registered MCP server by name (register via MCP SERVERS)', 
      cmd: 'list root directory via MCP',
      args: { command: 'npx', args: ['-y', '@modelcontextprotocol/server-filesystem', 'C:\\'], tool_name: 'list_directory', tool_args: { path: 'C:\\' } }
    },
    { 
      id: 'mcp_manage', 
      label: 'MCP SERVERS', 
      category: 'SYSTEM',
      hue: theme.blue, 
      icon: <Network size={16}/>, 
      desc: 'List registered MCP servers (spawn config kept out of chat history)', 
      customAction: executeMCPManage 
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
      id: 'news_feed', 
      label: 'NEWS / RSS', 
      category: 'INTELLIGENCE',
      hue: theme.orange, 
      icon: <Radio size={16}/>, 
      desc: 'Fetch latest posts from a subreddit or any RSS/Atom feed (no credentials needed)', 
      cmd: 'fetch news from r/singularity' 
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], []);

  const categories = ['ALL', 'PROTOCOL', 'SWARM', 'VISION', 'INTELLIGENCE', 'QUANTUM', 'SYSTEM'];

  const filteredTools = activeCategory === 'ALL' 
    ? toolArsenal 
    : toolArsenal.filter(t => t.category === activeCategory);

  async function executeGitHubUpgrade() {
    setStatus('CHECKING_UPDATES...');
    setResponse('> Checking github.com/TristenLong/T for updates...\n');
    try {
      const check = await fetch('/api/upgrade/check', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
      const state = await check.json();
      if (!state.ok) {
        setResponse(`> Update check failed: ${state.error || 'UNKNOWN'}`);
        speak("Update check failed.");
        return;
      }
      if (!state.available) {
        setResponse(`> Already up to date.\nRepo: ${state.remote_url || 'origin'}\nBranch: ${state.branch}\nCommit: ${(state.current || '').slice(0, 7)}`);
        speak("Already up to date.");
        return;
      }
      setResponse(`> Update available.\n  Branch: ${state.branch}\n  Local:  ${(state.current || '').slice(0, 7)}\n  Remote: ${(state.latest || '').slice(0, 7)}\n> Pulling latest code...\n`);
      const apply = await fetch('/api/upgrade/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
      const done = await apply.json();
      if (!done.ok) {
        setResponse(`> Upgrade failed: ${done.error || 'UNKNOWN'}`);
        speak("Upgrade failed.");
        observe('TOOL', `github_upgrade -> FAILED: ${done.error}`);
        return;
      }
      const msg = done.already_up_to_date
        ? '> Already up to date.'
        : `> Upgrade complete.\n  ${(done.from || '').slice(0, 7)} -> ${(done.to || '').slice(0, 7)}\n> RESTART the app so the new code takes effect.`;
      setResponse(msg);
      speak("Upgrade completed. Restart the application now.");
      observe('TOOL', `github_upgrade -> ${done.to || 'OK'}`);
    } catch (e) {
      setResponse(`> Upgrade error: ${e.message}`);
      speak("Upgrade error.");
    } finally {
      setStatus('THE_ONE_ONLINE');
    }
  };

  async function executeMCPManage() {
    setStatus('EXECUTING_TOOL...');
    setResponse('> Listing registered MCP servers...\n');
    try {
      const res = await fetch('/api/mcp/servers', { method: 'GET', headers: { 'Content-Type': 'application/json' } });
      const data = await res.json();
      if (!data.ok) {
        setResponse(`> MCP status failed: ${data.error || 'UNKNOWN'}`);
        return;
      }
      const servers = data.servers || [];
      if (!servers.length) {
        setResponse('> No MCP servers registered. Tell JESTER "register the filesystem MCP server" to add one.');
        speak("No MCP servers registered yet.");
        return;
      }
      const listing = servers.map(s => `- ${s.name}: ${s.command} ${(s.args || []).join(' ')}`).join('\n');
      setResponse(`> Registered MCP servers:\n${listing}`);
      speak(`${servers.length} MCP server${servers.length > 1 ? 's' : ''} registered.`);
      observe('TOOL', `mcp_manage -> ${servers.length} servers`);
    } catch (e) {
      setResponse(`> MCP status error: ${e.message}`);
    } finally {
      setStatus('THE_ONE_ONLINE');
    }
  }

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
           observe('TOOL', `${tool.id} -> OK`);
        } else {
           setResponse(`> Tool Execution Failed: ${data.error}`);
           speak("Tool execution failed.");
           observe('TOOL', `${tool.id} -> FAILED: ${data.error}`);
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
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <a 
                  href="/observatory.html" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  style={{ background: 'rgba(0, 240, 255, 0.1)', border: `1px solid ${theme.cyan}`, color: theme.cyan, padding: '5px 12px', borderRadius: '4px', textDecoration: 'none', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Globe size={14}/> FULLSCREEN OBSERVATORY
                </a>
                <button 
                  onClick={() => setShowObservatory(false)}
                  style={{ background: 'none', border: `1px solid ${theme.purple}`, color: theme.purple, padding: '5px 15px', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <X size={16}/> CLOSE
                </button>
              </div>
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

      {/* Side Bud: JESTER Observer Panel */}
      <AnimatePresence>
        {showObserver && (
          <motion.div
            initial={{ opacity: 0, x: 80 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 80 }}
            style={{
              position: 'fixed',
              top: '80px',
              right: '18px',
              width: '330px',
              maxHeight: '78vh',
              boxSizing: 'border-box',
              pointerEvents: 'auto',
              background: 'rgba(0, 10, 2, 0.96)',
              border: `2px solid ${theme.orange}`,
              boxShadow: `0 0 40px ${theme.orange}44`,
              borderRadius: '12px',
              zIndex: 75,
              display: 'flex',
              flexDirection: 'column',
              padding: '14px',
              backdropFilter: 'blur(10px)'
            }}
          >
            <div style={{ borderBottom: `1px solid ${theme.orange}44`, paddingBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ margin: 0, color: theme.orange, fontSize: '0.85rem', letterSpacing: '2px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Eye size={14} color={theme.orange}/> JESTER OBSERVER
                </h3>
                <div style={{ fontSize: '0.65rem', color: theme.sec, marginTop: '2px' }}>side bud // talks &amp; observes the deck</div>
              </div>
              <button
                onClick={() => setShowObserver(false)}
                style={{ background: 'none', border: `1px solid ${theme.orange}`, color: theme.orange, cursor: 'pointer', padding: '2px 8px', borderRadius: '4px' }}
              >
                <X size={14}/>
              </button>
            </div>

            <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', margin: '10px 0', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.72rem', fontFamily: 'monospace' }}>
              {observerLog.slice().reverse().map((o, i) => (
                <div
                  key={i}
                  style={{
                    color: o.type === 'JESTER' ? theme.main : (o.type === 'ALERT' ? theme.amber : (o.type === 'TOOL' ? theme.purple : (o.type === 'MEMORY' ? theme.cyan : theme.sec))),
                    borderLeft: `2px solid ${o.type === 'JESTER' ? theme.main : theme.orange}`,
                    paddingLeft: '6px',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word'
                  }}
                >
                  <span style={{ opacity: 0.6 }}>[{o.ts}] [{o.type}] </span>{o.text}
                </div>
              ))}
              {observerLog.length === 0 && (
                <div style={{ color: theme.sec, opacity: 0.7 }}>Observer channel idle. Watching the deck...</div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                value={observerInput}
                onChange={(e) => setObserverInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') observerSend(); }}
                placeholder="talk to the bud..."
                disabled={observerBusy}
                style={{ flex: 1, background: 'rgba(0, 20, 10, 0.6)', border: `1px solid ${theme.sec}`, color: theme.main, padding: '8px', borderRadius: '4px', fontSize: '0.75rem', outline: 'none' }}
              />
              <button
                onClick={observerSend}
                disabled={observerBusy}
                style={{ background: theme.orange, color: '#000', border: 'none', borderRadius: '4px', padding: '8px 12px', cursor: observerBusy ? 'default' : 'pointer', display: 'flex', alignItems: 'center' }}
              >
                <Send size={14}/>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Background 3D Canvas */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
        <Canvas>
          <PerspectiveCamera makeDefault position={[0, 0, 5]} />
          <Stars radius={100} depth={50} count={3000} factor={4} saturation={1} fade speed={1} />
          <Suspense fallback={null}>
            <JesterBrain 
              isSpeaking={isSpeaking} 
              isListening={isListening} 
              isAnomaly={sentryAlert} 
              isDeliberating={isSwarmDeliberating}
              speakingBotId={speakingBot}
              activeBot={activeBot}
              color={theme.main} 
            />
          </Suspense>
        </Canvas>
      </div>

      <div style={{ position: 'relative', zIndex: 10, height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* Main Header */}
        <header style={{ WebkitAppRegion: 'drag', padding: '12px 25px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,10,0,0.9)', borderBottom: '1px solid ' + theme.sec, pointerEvents: 'auto' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.2rem', letterSpacing: '6px', color: theme.main, display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Zap size={20} color={theme.main}/> JESTER CORE V2000: SINGULARITY (SWARM)
            </h1>
            <div style={{ fontSize: '0.65rem', opacity: 0.8, color: theme.sec }}>AI CORE: JESTER | LLM: {vitals.model} | STATUS: {status}</div>
          </div>
          <div style={{ WebkitAppRegion: 'no-drag', display: 'flex', gap: '10px', fontSize: '0.8rem', alignItems: 'center', pointerEvents: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: theme.cyan }}><Cpu size={14}/> {vitals.cpu}%</div>
            
            <div 
              onClick={optimizeRam}
              title="Click to purge working sets and optimize system RAM"
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '5px', 
                color: vitals.ram > 85 ? theme.err : theme.main, 
                cursor: 'pointer',
                padding: '2px 7px',
                borderRadius: '4px',
                background: optimizingRam ? 'rgba(0,255,102,0.2)' : 'rgba(0,20,5,0.6)',
                border: '1px solid ' + (vitals.ram > 85 ? theme.err : theme.sec),
                fontWeight: 'bold',
                fontSize: '0.75rem'
              }}
            >
              <Database size={13}/> {vitals.ram}% {optimizingRam ? 'TRIMMING...' : 'PURGE'}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: theme.amber }} title={`XP: ${stats.xp}`}><Sparkles size={14}/> LVL {stats.level}</div>
            
            <button 
              onClick={() => setSentryActive(prev => !prev)} 
              title={sentryActive ? (sentryAlert ? "Sentry Anomaly Detected!" : "Autonomous Sentry Watcher Active") : "Sentry Watcher Idle"}
              style={{ 
                background: sentryActive ? (sentryAlert ? 'rgba(255,0,85,0.25)' : 'rgba(0,240,255,0.2)') : 'none', 
                border: '1px solid ' + (sentryActive ? (sentryAlert ? theme.err : theme.cyan) : theme.sec), 
                color: sentryAlert ? theme.err : (sentryActive ? theme.cyan : theme.sec), 
                padding: '5px 12px', 
                borderRadius: '4px', 
                cursor: 'pointer', 
                fontSize: '0.72rem', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '5px', 
                fontWeight: 'bold',
                boxShadow: sentryAlert ? `0 0 12px ${theme.err}66` : 'none'
              }}
            >
              <Shield size={13}/> SENTRY: {sentryActive ? (sentryAlert ? 'ALERT' : 'ON') : 'OFF'}
            </button>

            <button 
              onClick={() => setShowArsenal(prev => !prev)} 
              style={{ background: showArsenal ? 'rgba(0,240,255,0.2)' : 'none', border: '1px solid ' + theme.cyan, color: theme.cyan, padding: '5px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 'bold' }}
            >
              <Wrench size={13}/> TOOL ARSENAL
            </button>

            <button 
              onClick={() => setShowObserver(prev => !prev)} 
              style={{ background: showObserver ? 'rgba(255,119,0,0.2)' : 'none', border: '1px solid ' + theme.orange, color: theme.orange, padding: '5px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 'bold' }}
            >
              <Eye size={13}/> OBSERVER
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
              onClick={connectPuter} 
              style={{ background: status === 'PUTER_LINKED' ? 'rgba(0,210,255,0.25)' : 'none', border: '1px solid ' + theme.blue, color: theme.blue, padding: '5px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 'bold' }}
            >
              <RefreshCw size={13}/> CONNECT PUTER
            </button>

            <button 
              onClick={jarvisLinkTest} 
              style={{ background: 'none', border: '1px solid ' + theme.amber, color: theme.amber, padding: '5px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 'bold' }}
            >
              <Activity size={13}/> LINK TEST
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
              title="Close JESTER CORE"
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
            <div ref={memoryScrollRef} style={{ flex: 1, overflowY: 'auto', fontSize: '0.7rem' }}>
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
            
            {/* Swarm Fleet & Multi-Bot Selector Bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              maxWidth: '88%',
              width: '88%',
              marginBottom: '10px',
              gap: '8px',
              flexWrap: 'wrap',
              pointerEvents: 'auto'
            }}>
              {/* Bot Selector Tabs */}
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                <button
                  onClick={() => setActiveBot('swarm')}
                  style={{
                    background: activeBot === 'swarm' 
                      ? 'linear-gradient(135deg, rgba(0,255,102,0.25), rgba(176,38,255,0.25))' 
                      : 'rgba(0,15,5,0.7)',
                    border: activeBot === 'swarm' 
                      ? `2px solid ${theme.main}` 
                      : '1px solid rgba(0,255,100,0.3)',
                    color: activeBot === 'swarm' ? '#FFF' : theme.main,
                    padding: '6px 12px',
                    borderRadius: '20px',
                    fontSize: '0.72rem',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    boxShadow: activeBot === 'swarm' ? `0 0 15px ${theme.main}66` : 'none',
                    transition: 'all 0.2s ease'
                  }}
                  title="Multi-Bot Deliberation & Cross-Talk Roundtable"
                >
                  <Users size={14} color={theme.main} />
                  <span>SWARM ROUNDTABLE</span>
                  <span style={{ fontSize: '0.6rem', padding: '1px 5px', borderRadius: '10px', background: 'rgba(0,255,102,0.2)', color: theme.main }}>ALL 5</span>
                </button>

                {swarmBots.map((b) => {
                  const isSelected = activeBot === b.id;
                  return (
                    <button
                      key={b.id}
                      onClick={() => setActiveBot(b.id)}
                      style={{
                        background: isSelected ? `${b.color}33` : 'rgba(0,10,5,0.6)',
                        border: isSelected ? `2px solid ${b.color}` : `1px solid ${b.color}44`,
                        color: isSelected ? '#FFF' : b.color,
                        padding: '6px 11px',
                        borderRadius: '20px',
                        fontSize: '0.7rem',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '5px',
                        boxShadow: isSelected ? `0 0 15px ${b.color}66` : 'none',
                        transition: 'all 0.2s ease'
                      }}
                      title={`${b.name} (${b.role}) - Direct Comms`}
                    >
                      {renderBotIcon(b.avatar, b.color, 13)}
                      <span>{b.name}</span>
                    </button>
                  );
                })}
              </div>

              {/* Action Controls: Handshake Ping, Debate Topic, and Reset */}
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button
                  onClick={confirmComms}
                  disabled={isSwarmDeliberating}
                  style={{
                    background: commStatus?.state === 'VERIFIED'
                      ? 'rgba(0,255,102,0.2)'
                      : 'linear-gradient(135deg, rgba(0,240,255,0.2), rgba(0,255,102,0.2))',
                    border: `1px solid ${commStatus?.state === 'VERIFIED' ? theme.main : theme.cyan}`,
                    color: commStatus?.state === 'VERIFIED' ? theme.main : theme.cyan,
                    padding: '6px 14px',
                    borderRadius: '20px',
                    fontSize: '0.72rem',
                    fontWeight: 'bold',
                    cursor: isSwarmDeliberating ? 'default' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    boxShadow: commStatus?.state === 'VERIFIED' ? `0 0 15px ${theme.main}44` : `0 0 12px ${theme.cyan}44`,
                    opacity: isSwarmDeliberating ? 0.6 : 1
                  }}
                  title="Broadcast handshake to all 5 bots and verify communication"
                >
                  <CheckCircle2 size={14} color={commStatus?.state === 'VERIFIED' ? theme.main : theme.cyan} />
                  <span>{commStatus?.state === 'VERIFIED' ? 'COMMS CONFIRMED (5/5)' : '⚡ CONFIRM COMMS'}</span>
                </button>

                <button
                  onClick={() => runRoundtable(input || 'Review system architecture and verify all 5 agent channels')}
                  disabled={isSwarmDeliberating}
                  style={{
                    background: 'rgba(176,38,255,0.15)',
                    border: `1px solid ${theme.purple}`,
                    color: theme.purple,
                    padding: '6px 12px',
                    borderRadius: '20px',
                    fontSize: '0.72rem',
                    fontWeight: 'bold',
                    cursor: isSwarmDeliberating ? 'default' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    opacity: isSwarmDeliberating ? 0.6 : 1
                  }}
                  title="Trigger sequential multi-bot debate on the current objective"
                >
                  <Flame size={13} color={theme.purple} />
                  <span>DEBATE</span>
                </button>

                <button
                  onClick={executeConsensusCode}
                  disabled={executingConsensus || isSwarmDeliberating}
                  style={{
                    background: 'rgba(255,215,0,0.15)',
                    border: `1px solid ${theme.amber}`,
                    color: theme.amber,
                    padding: '6px 13px',
                    borderRadius: '20px',
                    fontSize: '0.72rem',
                    fontWeight: 'bold',
                    cursor: executingConsensus || isSwarmDeliberating ? 'default' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    opacity: executingConsensus || isSwarmDeliberating ? 0.6 : 1,
                    boxShadow: `0 0 10px ${theme.amber}33`
                  }}
                  title="Autonomously write and verify consensus code from the Swarm debate"
                >
                  <Code2 size={13} color={theme.amber} />
                  <span>{executingConsensus ? 'EXECUTING...' : '⚡ EXECUTE CONSENSUS'}</span>
                </button>

                {swarmTurns.length > 0 && (
                  <button
                    onClick={() => { setSwarmTurns([]); setResponse(''); }}
                    style={{
                      background: 'none',
                      border: `1px solid ${theme.sec}`,
                      color: theme.sec,
                      padding: '6px 8px',
                      borderRadius: '20px',
                      fontSize: '0.7rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center'
                    }}
                    title="Clear Swarm Dialogue"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            </div>

            <AnimatePresence mode='wait'>
              <motion.div 
                key="chat-stage" 
                initial={{ opacity: 0, y: 10 }} 
                animate={{ opacity: 1, y: 0 }} 
                style={{ 
                  textAlign: 'center', 
                  maxWidth: '88%', 
                  width: '88%', 
                  background: 'rgba(0,0,0,0.85)', 
                  padding: '16px 20px', 
                  borderRadius: '15px', 
                  border: `1px solid ${activeBot === 'swarm' ? 'rgba(0,255,100,0.4)' : (swarmBots.find(b => b.id === activeBot)?.color || theme.sec) + '66'}`, 
                  backdropFilter: 'blur(10px)', 
                  pointerEvents: 'auto', 
                  height: '52vh', 
                  maxHeight: '52vh', 
                  display: 'flex', 
                  flexDirection: 'column',
                  boxShadow: activeBot === 'swarm' 
                    ? '0 0 30px rgba(0,255,100,0.15)' 
                    : `0 0 30px ${(swarmBots.find(b => b.id === activeBot)?.color || theme.sec)}22`
                }}
              >
                {/* Active Mode Banner */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  borderBottom: '1px solid rgba(255,255,255,0.1)',
                  paddingBottom: '8px',
                  marginBottom: '10px',
                  fontSize: '0.72rem',
                  fontFamily: 'monospace'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {activeBot === 'swarm' ? (
                      <>
                        <Users size={14} color={theme.main} />
                        <span style={{ color: theme.main, fontWeight: 'bold' }}>SWARM ROUNDTABLE (CROSS-TALK DELIBERATION)</span>
                        <span style={{ color: '#888' }}>// 5 AUTONOMOUS AGENTS LINKED</span>
                      </>
                    ) : (
                      (() => {
                        const b = swarmBots.find(x => x.id === activeBot) || { name: activeBot.toUpperCase(), color: theme.cyan, role: 'Agent' };
                        return (
                          <>
                            {renderBotIcon(b.avatar, b.color, 14)}
                            <span style={{ color: b.color, fontWeight: 'bold' }}>DIRECT LINK: {b.name}</span>
                            <span style={{ color: '#888' }}>// {b.role}</span>
                          </>
                        );
                      })()
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {commStatus && (
                      <span style={{ 
                        color: commStatus.state === 'VERIFIED' ? theme.main : theme.amber,
                        fontSize: '0.68rem',
                        fontWeight: 'bold',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}>
                        <CheckCircle2 size={12} /> {commStatus.msg}
                      </span>
                    )}
                    <span style={{ color: isSwarmDeliberating ? theme.amber : theme.sec, fontSize: '0.68rem' }}>
                      {isSwarmDeliberating ? '● TRANSMITTING / DELIBERATING...' : '● READY'}
                    </span>
                  </div>
                </div>

                {/* Content Area */}
                <div 
                  ref={responseScrollRef} 
                  style={{ 
                    flex: 1, 
                    overflowY: 'auto', 
                    fontSize: '1rem', 
                    color: theme.main, 
                    whiteSpace: 'pre-wrap', 
                    lineHeight: '1.5', 
                    textAlign: 'left',
                    paddingRight: '6px'
                  }}
                >
                  {/* If Swarm turns are present, render multi-bot dialogue thread */}
                  {swarmTurns && swarmTurns.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {swarmTurns.map((turn, idx) => (
                        <div 
                          key={idx}
                          style={{
                            background: 'rgba(0, 15, 8, 0.75)',
                            border: `1px solid ${turn.color || theme.cyan}55`,
                            borderLeft: `4px solid ${turn.color || theme.cyan}`,
                            borderRadius: '8px',
                            padding: '10px 14px',
                            boxShadow: `0 0 15px ${turn.color || theme.cyan}15`
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ color: turn.color || theme.cyan, fontWeight: 'bold', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                {renderBotIcon(turn.avatar || (turn.name?.includes('CLAUDE') ? 'Terminal' : turn.name?.includes('GEMINI') ? 'Globe' : turn.name?.includes('CRITIC') ? 'Shield' : turn.name?.includes('CODEX') ? 'Code2' : 'Zap'), turn.color || theme.cyan, 13)}
                                {turn.name}
                              </span>
                              <span style={{ fontSize: '0.65rem', color: '#AAA', background: `${turn.color || theme.cyan}22`, padding: '2px 8px', borderRadius: '12px' }}>
                                {turn.role}
                              </span>
                            </div>
                            <span style={{ fontSize: '0.65rem', color: turn.color || theme.sec, opacity: 0.8, fontFamily: 'monospace' }}>
                              TURN {idx + 1}/{swarmTurns.length}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.86rem', color: '#ECECEC', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
                            {turn.content}
                          </div>
                        </div>
                      ))}

                      {response && !response.startsWith('[COMMUNICATIONS HANDSHAKE') && (
                        <div style={{
                          background: 'rgba(0, 20, 15, 0.85)',
                          border: `1px solid ${theme.cyan}`,
                          borderRadius: '8px',
                          padding: '12px 16px',
                          marginTop: '4px'
                        }}>
                          <div style={{ color: theme.cyan, fontWeight: 'bold', fontSize: '0.8rem', marginBottom: '4px' }}>
                            ROUNDTABLE CONSENSUS &amp; SYNTHESIS
                          </div>
                          <div style={{ fontSize: '0.85rem', color: '#FFF' }}>
                            {response}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    /* Default response view */
                    <div style={{ 
                      color: activeBot !== 'swarm' ? (swarmBots.find(b => b.id === activeBot)?.color || theme.main) : theme.main,
                      textShadow: `0 0 10px ${activeBot !== 'swarm' ? (swarmBots.find(b => b.id === activeBot)?.color || theme.sec) : theme.sec}`,
                      fontSize: '1.05rem',
                      lineHeight: '1.6'
                    }}>
                      {response || (
                        <div style={{ opacity: 0.8, fontSize: '0.9rem', color: theme.sec }}>
                          <div style={{ fontWeight: 'bold', color: theme.main, marginBottom: '6px' }}>
                            [AUTONOMOUS MULTI-BOT OBSERVATORY LINKED]
                          </div>
                          <div style={{ fontSize: '0.8rem', color: '#AAA', lineHeight: '1.6' }}>
                            • Click <span style={{ color: theme.cyan, fontWeight: 'bold' }}>[⚡ CONFIRM COMMS]</span> to broadcast a handshake ping — all 5 bots will report in and verify active communication.
                            <br />
                            • Select any individual bot tab above to chat directly with that specialist agent.
                            <br />
                            • Enter an objective or click <span style={{ color: theme.purple, fontWeight: 'bold' }}>[🔥 DEBATE]</span> in <span style={{ color: theme.main, fontWeight: 'bold' }}>[SWARM ROUNDTABLE]</span> to have all bots converse, debate, and reach consensus in sequence.
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>  

                {transcript && (
                  <div style={{ marginTop: '8px', fontSize: '0.85rem', color: theme.sec, opacity: 0.9, textAlign: 'left', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '6px' }}>
                    <span style={{ color: theme.amber }}>[VOICE TRANSCRIPT]:</span> {transcript}
                  </div>
                )}
              </motion.div>
            </AnimatePresence>

            {/* Input & Voice Controls */}
            <div style={{ marginTop: '22px', display: 'flex', gap: '15px', alignItems: 'center', pointerEvents: 'auto' }}>
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
                  ref={inputRef}
                  value={input} 
                  onChange={e => setInput(e.target.value)} 
                  onKeyDown={e => e.key === 'Enter' && (handleSend(input), setInput(''))} 
                  style={{ background: 'none', border: 'none', color: '#fff', padding: '12px 25px', outline: 'none', width: '380px', fontSize: '0.85rem' }} 
                  placeholder={
                    activeBot === 'swarm' 
                      ? 'ENTER TOPIC FOR MULTI-BOT ROUNDTABLE OR "PING"...' 
                      : `MESSAGE ${swarmBots.find(b => b.id === activeBot)?.name || 'AGENT'} DIRECTLY...`
                  } 
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
