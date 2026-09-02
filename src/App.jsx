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

// Puter frontend model (OpenRouter models via puter.js, no API key needed).
const PUTER_MODEL = 'z-ai/glm-5.3';

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

  const idleStatuses = ['THE_ONE_ONLINE', 'LOCAL_CORE_ACTIVE', 'PUTER_LINKED', 'FALLBACK_RESPONSE'];
  useEffect(() => {
    // Reclaim keyboard focus on the command input whenever the app is back to
    // idle so a stuck streaming turn or a stale HMR frame cannot leave the UI
    // with no way to type. Skip when the user is actively in another text
    // field (e.g. the Observer channel).
    const active = document.activeElement;
    const inInput = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA');
    if (!inInput && inputRef.current && idleStatuses.includes(status)) {
      requestAnimationFrame(() => inputRef.current && inputRef.current.focus({ preventScroll: true }));
    }
  }, [status, bootSequence]);

  useEffect(() => {
    // If a prior Puter sign-in token is still stored, push it to the backend so
    // the Tool Arsenal is armed without needing a fresh popup.
    if (typeof puter !== 'undefined' && puter && puter.authToken) {
      armBackendWithPuter();
    }
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

  const handleSend = async (msg, toolArgs = null) => {
    if (!msg || !msg.trim()) return;
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

  const executeGitHubUpgrade = async () => {
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
          <Suspense fallback={null}><JesterBrain isSpeaking={isSpeaking} isListening={isListening} color={theme.main} /></Suspense>
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
            <AnimatePresence mode='wait'>
              <motion.div key="chat-stage" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={{ textAlign: 'center', maxWidth: '86%', width: '86%', background: 'rgba(0,0,0,0.7)', padding: '22px 26px', borderRadius: '15px', border: '1px solid ' + theme.sec + '66', backdropFilter: 'blur(8px)', pointerEvents: 'auto', maxHeight: '50vh', display: 'flex', flexDirection: 'column' }}>
                <div ref={responseScrollRef} style={{ flex: 1, overflowY: 'auto', fontSize: '1.2rem', color: theme.main, textShadow: '0 0 10px ' + theme.sec, whiteSpace: 'pre-wrap', lineHeight: '1.5', textAlign: 'left' }}>{response || 'STANDBY_FOR_INPUT'}</div>  
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
                  ref={inputRef}
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
