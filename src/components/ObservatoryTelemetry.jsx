import React, { useState, useEffect, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const MAX_POINTS = 200;

export default function ObservatoryTelemetry({ onAnomalyChange }) {
  const [metrics, setMetrics] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [history, setHistory] = useState([]);
  const [fftData, setFftData] = useState([0, 0, 0, 0, 0]);
  const [isAnomaly, setIsAnomaly] = useState(false);
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [logs, setLogs] = useState([]);

  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const oscillatorRef = useRef(null);
  const gainNodeRef = useRef(null);
  const alarmRef = useRef(null);
  const alarmPlayedRef = useRef(false);

  useEffect(() => {
    alarmRef.current = new Audio('https://actions.google.com/sounds/v1/alarms/spaceship_alarm.ogg');
    
    wsRef.current = new WebSocket('ws://localhost:8765');
    wsRef.current.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type !== 'science_telemetry') return;

        const m = payload.metrics;
        const a = payload.analytics;
        setMetrics(m);
        setAnalytics(a);
        
        const anomaly = a.anomaly_detected || false;
        
        if (anomaly !== isAnomaly) {
            setIsAnomaly(anomaly);
            if (onAnomalyChange) onAnomalyChange(anomaly);
        }

        setHistory(prev => {
          const newHistory = [...prev, {
            entropy: m.shannon_entropy || 0,
            anomaly: anomaly
          }];
          if (newHistory.length > MAX_POINTS) newHistory.shift();
          return newHistory;
        });

        const newLog = {
          time: new Date(payload.timestamp * 1000).toLocaleTimeString(),
          entropy: (m.shannon_entropy || 0).toFixed(4),
          ml: a.ml_anomaly_score || 0,
          fft: a.fft_dominant_amplitude || 0,
          anomaly
        };
        setLogs(prev => [newLog, ...prev].slice(0, 50));

        setFftData([
            Math.random() * (a.fft_dominant_amplitude || 1),
            Math.random() * (a.fft_dominant_amplitude || 1) * 2,
            a.fft_dominant_amplitude || 0,
            Math.random() * (a.fft_dominant_amplitude || 1) * 1.5,
            Math.random() * (a.fft_dominant_amplitude || 1) * 0.5
        ]);

        if (audioEnabled && audioCtxRef.current && oscillatorRef.current) {
            if (anomaly) {
                if (!alarmPlayedRef.current) {
                    alarmRef.current.play().catch(()=>console.log("audio blocked"));
                    alarmPlayedRef.current = true;
                }
                oscillatorRef.current.frequency.setTargetAtTime(800 + ((a.fft_dominant_amplitude || 0) * 100), audioCtxRef.current.currentTime, 0.1);
                oscillatorRef.current.type = 'sawtooth';
            } else {
                alarmPlayedRef.current = false;
                oscillatorRef.current.frequency.setTargetAtTime(432 + (((m.shannon_entropy || 7.95) - 7.95) * 1000), audioCtxRef.current.currentTime, 0.5);
                oscillatorRef.current.type = 'sine';
            }
        }

      } catch (err) {
        console.error("WS Parse Error", err);
      }
    };

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [audioEnabled, isAnomaly, onAnomalyChange]);

  const toggleAudio = () => {
    if (!audioEnabled) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioCtxRef.current = new AudioContext();
      oscillatorRef.current = audioCtxRef.current.createOscillator();
      gainNodeRef.current = audioCtxRef.current.createGain();
      oscillatorRef.current.type = 'sine';
      oscillatorRef.current.frequency.value = 432;
      gainNodeRef.current.gain.value = 0.05;
      oscillatorRef.current.connect(gainNodeRef.current);
      gainNodeRef.current.connect(audioCtxRef.current.destination);
      oscillatorRef.current.start();
      setAudioEnabled(true);
    } else {
        if (oscillatorRef.current) {
            oscillatorRef.current.stop();
            oscillatorRef.current.disconnect();
        }
        if (audioCtxRef.current) {
            audioCtxRef.current.close();
        }
        setAudioEnabled(false);
    }
  };

  const lineChartData = {
    labels: Array(history.length).fill(''),
    datasets: [{
        label: 'Shannon Entropy',
        data: history.map(h => h.entropy),
        borderColor: '#00ff88',
        backgroundColor: 'rgba(0,255,136,0.1)',
        fill: true,
        pointRadius: history.map(h => h.anomaly ? 4 : 0),
        pointBackgroundColor: history.map(h => h.anomaly ? '#ff3366' : '#00ff88'),
        borderWidth: 2,
        tension: 0.1
    }]
  };

  const lineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { x: { display: false }, y: { display: false } },
    animation: false,
    layout: { padding: 0 }
  };

  const barChartData = {
    labels: ['F1', 'F2', 'F3', 'F4', 'F5'],
    datasets: [{
      label: 'FFT Amplitude',
      data: fftData,
      backgroundColor: '#b026ff',
      borderWidth: 0
    }]
  };
  
  const barOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { x: { display: false }, y: { display: false, max: Math.max(...fftData) * 1.5 || 1 } },
    animation: false
  };

  const m = metrics || {};
  const a = analytics || {};

  const kpPercent = Math.min((m.geomagnetic_kp || 0) / 9 * 100, 100);
  const jesterCoh = isAnomaly ? (60 + Math.random()*20) : (98 + Math.random()*2);

  return (
    <>
      <div style={{ position: 'fixed', bottom: '20px', right: '20px', zIndex: 1000 }}>
        <button onClick={toggleAudio} style={{ 
          background: audioEnabled ? '#00ff88' : 'transparent', 
          color: audioEnabled ? '#000' : '#00e5ff', 
          border: '1px solid #00e5ff', 
          padding: '8px 16px', fontSize: '12px', cursor: 'pointer', fontFamily: 'Orbitron'
        }}>
          {audioEnabled ? 'SONIFICATION ACTIVE' : 'ENABLE SONIFICATION'}
        </button>
      </div>

      {isAnomaly && (
        <div className="anomaly-banner show" style={{ display: 'flex' }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
          SYSTEM ANOMALY DETECTED — CORRELATION OR FREQUENCY THRESHOLD EXCEEDED
        </div>
      )}

      {/* Charts */}
      <div className="panel chart-panel">
        <div className="chart-header">
          <div className="panel-label">
            <span>REAL-TIME ENTROPY TRACE (H)</span>
            <span className="tag">SOURCE: {(m.entropy_source || 'SCANNING...').toUpperCase()}</span>
          </div>
        </div>
        <div style={{ height: '200px', width: '100%', position: 'relative' }}>
            <Line data={lineChartData} options={lineOptions} />
        </div>
      </div>
      
      <div className="panel chart-panel-small">
        <div className="panel-label">
          <span>QUANTUM FFT FREQUENCY</span>
          <span className="tag" style={{color: 'var(--accent-purple)', borderColor: 'var(--accent-purple)'}}>AMPLITUDE</span>
        </div>
        <div style={{ height: '180px', width: '100%', position: 'relative' }}>
            <Bar data={barChartData} options={barOptions} />
        </div>
      </div>

      {/* Row 1 Metrics */}
      <div className="panel col-4">
        <div className="panel-label"><span>QUANTUM ENTROPY</span></div>
        <div className="big-readout">{(m.shannon_entropy || 0).toFixed(4)}<span className="unit">bits</span></div>
        <div className="sub-readout">Z-SCORE: <b style={{color: 'var(--accent-cyan)'}}>{a.rolling_z_score || '0.00'}</b> | ML SCORE: <b style={{color: 'var(--accent-purple)'}}>{a.ml_anomaly_score || '0'}</b></div>
      </div>

      <div className="panel col-4">
        <div className="panel-label"><span>SOLAR FLARE X-RAY</span></div>
        <div className="big-readout">{(m.xray_flux || 0).toExponential(2).toUpperCase()}<span className="unit">W/m²</span></div>
        <div className="sub-readout">NOAA GOES-16 0.1-0.8nm</div>
      </div>

      <div className="panel col-4">
        <div className="panel-label"><span>JESTER COHERENCE</span></div>
        <div className="big-readout">{jesterCoh.toFixed(0)}<span className="unit">%</span></div>
        <div className="gauge-container">
          <div className="gauge-track"><div className="gauge-fill" style={{width: `${jesterCoh}%`, background: 'var(--accent-green)'}}></div></div>
        </div>
        <div className="sub-readout">COGNITIVE LOAD: <b style={{color: isAnomaly ? 'var(--accent-red)' : 'var(--accent-green)'}}>{isAnomaly ? 'ANOMALOUS' : 'IDLE'}</b></div>
      </div>

      {/* Row 2 Metrics */}
      <div className="panel col-3">
        <div className="panel-label"><span>SYSTEM CPU</span></div>
        <div className="big-readout">{(m.os_cpu_percent || 0).toFixed(1)}<span className="unit">%</span></div>
        <div className="gauge-container">
          <div className="gauge-track"><div className="gauge-fill" style={{width: `${m.os_cpu_percent || 0}%`, background: 'var(--accent-green)'}}></div></div>
        </div>
        <div className="sub-readout">THREADS USAGE</div>
      </div>
      
      <div className="panel col-3">
        <div className="panel-label"><span>SYSTEM RAM</span></div>
        <div className="big-readout">{(m.os_ram_percent || 0).toFixed(1)}<span className="unit">%</span></div>
        <div className="gauge-container">
          <div className="gauge-track"><div className="gauge-fill" style={{width: `${m.os_ram_percent || 0}%`, background: 'var(--accent-purple)'}}></div></div>
        </div>
        <div className="sub-readout">VIRTUAL MEMORY</div>
      </div>

      <div className="panel col-3">
        <div className="panel-label"><span>DISK I/O</span></div>
        <div className="big-readout">{(m.os_disk_percent || 0).toFixed(1)}<span className="unit">%</span></div>
        <div className="gauge-container">
          <div className="gauge-track"><div className="gauge-fill" style={{width: `${m.os_disk_percent || 0}%`, background: 'var(--accent-gold)'}}></div></div>
        </div>
        <div className="sub-readout">ROOT STORAGE</div>
      </div>

      <div className="panel col-3">
        <div className="panel-label"><span>NETWORK IN</span></div>
        <div className="big-readout">{(m.os_net_recv_rate || 0).toFixed(2)}<span className="unit">MB/s</span></div>
        <div className="sub-readout">OUT: <b style={{color: 'var(--accent-cyan)'}}>{(m.os_net_sent_rate || 0).toFixed(2)}</b> MB/s</div>
      </div>

      {/* Logs */}
      <div className="panel col-12" style={{ maxHeight: '250px', overflowY: 'auto' }}>
        <div className="panel-label"><span>SYSTEM TELEMETRY LOG</span></div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.8' }}>
          {logs.map((log, i) => (
            <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.02)', color: log.anomaly ? 'var(--accent-gold)' : 'inherit' }}>
              <span style={{ color: 'var(--accent-green)', opacity: 0.7 }}>[{log.time}]</span> SYSTEM_TICK: H=<span style={{color: log.anomaly ? 'var(--accent-red)' : 'var(--text-main)'}}>{log.entropy}</span> | ML=<span style={{color: log.anomaly ? 'var(--accent-red)' : 'var(--text-main)'}}>{log.ml}</span> | FFT_AMP=<span style={{color: log.anomaly ? 'var(--accent-red)' : 'var(--text-main)'}}>{log.fft}</span>
              {log.anomaly && <span> ⚠ <span style={{color: 'var(--accent-red)'}}>[ANOMALY_TRIGGERED]</span></span>}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
