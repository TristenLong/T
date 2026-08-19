import React, { useState, useEffect, useRef, Suspense, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, MeshDistortMaterial, Float, Stars, PerspectiveCamera, Torus, MeshWobbleMaterial } from '@react-three/drei';

function OmnipresentCore() {
  const outer = useRef();
  const inner = useRef();
  
  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (outer.current) {
        outer.current.rotation.x = t * 0.3;
        outer.current.rotation.y = t * 0.4;
    }
    if (inner.current) {
        inner.current.rotation.x = -t * 0.6;
        inner.current.rotation.z = t * 0.5;
        const s = 1 + Math.sin(t * 2) * 0.05;
        inner.current.scale.set(s, s, s);
    }
  });

  return (
    <group>
      <Float speed={5} rotationIntensity={2} floatIntensity={2}>
        <mesh ref={outer}>
          <torusKnotGeometry args={[1.2, 0.4, 128, 32]} />
          <MeshDistortMaterial
            color='#00FBFF'
            speed={3}
            distort={0.4}
            radius={1}
            wireframe
          />
        </mesh>
      </Float>
      <mesh ref={inner}>
        <sphereGeometry args={[0.6, 64, 64]} />
        <MeshWobbleMaterial
          color='#00FF41'
          speed={5}
          factor={0.6}
          wireframe
        />
      </mesh>
    </group>
  );
}

const MatrixRain = () => {
  const canvasRef = useRef();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$+-*/=%#&_(),.;:?!\\|{}<>[]^~';
    const fontSize = 16;
    const columns = canvas.width / fontSize;
    const drops = Array(Math.floor(columns)).fill(1);

    const draw = () => {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#00FBFF33';
      ctx.font = `${fontSize}px monospace`;

      for (let i = 0; i < drops.length; i++) {
        const text = chars.charAt(Math.floor(Math.random() * chars.length));
        ctx.fillText(text, i * fontSize, drops[i] * fontSize);
        if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
          drops[i] = 0;
        }
        drops[i]++;
      }
    };

    const interval = setInterval(draw, 33);
    return () => clearInterval(interval);
  }, []);

  return <canvas ref={canvasRef} style={{ position: 'absolute', top: 0, left: 0, opacity: 0.3, pointerEvents: 'none' }} />;
};

function App() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [vitals, setVitals] = useState({ cpu: 0, ram: 0, persona: 'OMNIPRESENT' });
  const [isProcessing, setIsProcessing] = useState(false);
  const recognitionRef = useRef(null);
  const tts = window.speechSynthesis;
  const [voices, setVoices] = useState([]);

  useEffect(() => {
    const loadVoices = () => {
      const v = tts.getVoices();
      setVoices(v);
    };
    loadVoices();
    tts.onvoiceschanged = loadVoices;
  }, []);

  const speak = (text) => {
    tts.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    const preferredVoice = voices.find(v => v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Female')) || voices[0];
    if (preferredVoice) utt.voice = preferredVoice;
    utt.pitch = 1.2; 
    utt.rate = 1.05;
    tts.speak(utt);
  };

  useEffect(() => {
    console.log('JESTER_V43_OMNIPRESENT_ONLINE');
    const pulse = () => {
      fetch('/api/pulse').then(res => res.json()).then(setVitals).catch(err => console.error('Pulse error:', err));
    };
    const intv = setInterval(pulse, 1500);
    pulse();

    setTimeout(() => {
      const greeting = 'Neural link synchronized. I am JESTER V43: THE OMNIPRESENT. The display matrix has been expanded. Communication protocols are at peak efficiency.';
      setResponse(greeting);
      speak(greeting);
    }, 2000);

    return () => clearInterval(intv);
  }, [voices]);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.onresult = (e) => {
        let final = '';
        for (let i = e.resultIndex; i < e.results.length; ++i) {
          if (e.results[i].isFinal) final += e.results[i][0].transcript;
        }
        if (final) handleInput(final);
      };
      recognitionRef.current.onstart = () => setIsListening(true);
      recognitionRef.current.onend = () => setIsListening(false);
    }
  }, []);

  const handleInput = async (msg) => {
    if(!msg.trim()) return;
    setTranscript(msg);
    setIsProcessing(true);
    setResponse('');
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      });
      const data = await res.json();
      setResponse(data.response);
      speak(data.response);
    } catch (err) {
      const errS = 'OMNIPRESENT_DESYNC: RE-INTEGRATING COGNITIVE LAYERS...';
      setResponse(errS);
      speak(errS);
    } finally { setIsProcessing(false); }
  };

  const themeColor = '#00FBFF'; 

  return (
    <div style={{
      backgroundColor: '#000', color: themeColor, height: '100vh', width: '100vw',
      display: 'flex', flexDirection: 'column', fontFamily: 'Orbitron, sans-serif',
      overflow: 'hidden'
    }}>
      <MatrixRain />
      
      <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 0 }}>
        <Canvas>
          <PerspectiveCamera makeDefault position={[0, 0, 6]} />
          <Stars radius={150} depth={50} count={15000} factor={10} saturation={1} fade speed={4} />
          <ambientLight intensity={0.2} />
          <pointLight position={[10, 10, 10]} color={themeColor} intensity={2} />
          <Suspense fallback={null}>
            <OmnipresentCore />
          </Suspense>
        </Canvas>
      </div>

      <header style={{ zIndex: 1, padding: '20px 40px', borderBottom: `1px solid ${themeColor}66`, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(30px)' }}>
        <div>
          <h1 style={{ margin: 0, letterSpacing: '15px', fontWeight: 900, textShadow: `0 0 25px ${themeColor}`, color: themeColor, fontSize: '1.5rem' }}>JESTER_V43_OMNIPRESENT</h1>
          <div style={{ fontSize: '0.6rem', letterSpacing: '4px', opacity: 0.7 }}>NEXUS_POINT_CONNECTED</div>
        </div>
        <div style={{ fontSize: '0.8rem', textAlign: 'right', fontWeight: 'bold', textShadow: `0 0 10px ${themeColor}44` }}>
          CPU: {vitals.cpu}% | RAM: {vitals.ram}% | STATUS: {vitals.persona}_PROTOCOL<br/>
          <span style={{ color: '#00FF41' }}>UPLINK: TRANSCENDENT</span>
        </div>
      </header>

      <main style={{ zIndex: 1, flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', padding: '40px' }}>
        <div style={{
          width: '100%', maxWidth: '1200px', background: 'rgba(0,5,10,0.9)',
          border: `1px solid ${themeColor}`, borderRadius: '0', padding: '60px',
          textAlign: 'left', backdropFilter: 'blur(50px)', marginBottom: '30px',
          boxShadow: `0 0 60px ${themeColor}22`, position: 'relative'
        }}>
          <div style={{ position: 'absolute', top: '10px', right: '15px', fontSize: '0.6rem', opacity: 0.3 }}>DATA_STREAM_V43.0.0</div>
          <div style={{ fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '20px', color: '#00FF41', letterSpacing: '8px', fontWeight: 900 }}>
            {isProcessing ? 'OMNIPRESENT_CALCULATION_IN_PROGRESS...' : 'TRANSCENDENT_COMMUNIQUE'}
          </div>
          <div style={{ fontSize: '2rem', lineHeight: '1.3', minHeight: '150px', color: '#fff', fontWeight: 700, textShadow: `0 0 15px ${themeColor}88` }}>
            {response || 'AWAITING_NEURAL_COMMANDS.'}
          </div>
          <div style={{ marginTop: '40px', color: themeColor, fontSize: '1.1rem', borderTop: `1px solid ${themeColor}44`, paddingTop: '25px', fontStyle: 'normal', opacity: 0.8, fontFamily: 'monospace' }}>
             {transcript ? `> NODE_INPUT: ${transcript}` : '> AWAITING_SIGNAL_FROM_USER_NODE...'}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '30px', width: '100%', maxWidth: '1200px' }}>
          <button
            onClick={() => isListening ? recognitionRef.current.stop() : recognitionRef.current.start()}
            style={{
              padding: '25px 60px', background: isListening ? themeColor : 'transparent',
              color: isListening ? '#000' : themeColor, border: `2px solid ${themeColor}`,
              cursor: 'pointer', fontWeight: 900, fontSize: '1.2rem', letterSpacing: '8px',
              transition: 'all 0.3s cubic-bezier(0.19, 1, 0.22, 1)', textTransform: 'uppercase',
              boxShadow: isListening ? `0 0 40px ${themeColor}` : 'none'
            }}
          >
            {isListening ? 'SILENCE_NODES' : 'INITIATE_UPLINK'}
          </button>
          <input
            type='text'
            placeholder='EXECUTE_OMNIPRESENT_COMMAND...'
            onKeyDown={e => { if(e.key === 'Enter') { handleInput(e.target.value); e.target.value = ''; } }}
            style={{
              flex: 1, background: 'rgba(0,251,255,0.05)', border: `2px solid ${themeColor}`,
              padding: '0 40px', color: '#fff', outline: 'none', fontSize: '1.3rem',
              fontFamily: 'Orbitron, sans-serif', letterSpacing: '3px'
            }}
          />
        </div>
      </main>

      <footer style={{ zIndex: 1, padding: '20px', textAlign: 'center', fontSize: '0.9rem', color: themeColor, borderTop: `1px solid ${themeColor}33`, background: 'rgba(0,0,0,0.9)', letterSpacing: '6px', fontWeight: 'bold' }}>
        [ JESTER_V43 : THE_OMNIPRESENT ] | NEURAL_BRIDGE: ACTIVE | OMNISCIENCE: ENABLED
      </footer>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        body { margin: 0; background: #000; overflow: hidden; }
        button:hover { background: ${themeColor}; color: #000; box-shadow: 0 0 30px ${themeColor}; transform: translateY(-2px); }
        ::placeholder { color: ${themeColor}44; }
      `}</style>
    </div>
  );
}

export default App;
