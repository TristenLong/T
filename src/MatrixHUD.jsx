import React, { useState, useEffect } from 'react';
import { Cpu, Zap, Activity, Bot, Network, Globe, HeartPulse, Radio } from 'lucide-react';

const MatrixHUD = ({ theme, onClose, stats: externalStats }) => {
  const defaultStats = { 
    swarm: { swarm_status: 'ACTIVE', subagents: ['Architect', 'Navigator'], status: 'ONLINE' },
    cpu: 0, ram: 0, ai_status: 'CHECKING',
    sync_potential: 0, gcp_variance: 'Unknown', local_coherence: 0, forecast: 'Calculating...',
    taijitu: { yin: 50, yang: 50 }
  };
  
  const stats = {
    ...defaultStats,
    ...(externalStats || {}),
    taijitu: { ...defaultStats.taijitu, ...(externalStats?.taijitu || {}) },
  };

  const syncColor = stats.sync_potential > 85 ? theme.main : (stats.sync_potential > 40 ? theme.sec : theme.err);
  const isYangDominant = stats.taijitu?.yang > 60;
  const isYinDominant = stats.taijitu?.yin > 60;
  const balanceTheme = isYangDominant ? '#ffdd55' : (isYinDominant ? '#7755ff' : theme.main);
  
  const style = {
    container: {
      position: 'absolute',
      top: '20px',
      right: '20px',
      width: '320px',
      background: 'rgba(5, 10, 5, 0.9)',
      border: `1px solid ${syncColor}`,
      borderRadius: '12px',
      padding: '20px',
      color: theme.main,
      fontFamily: '"Courier New", Courier, monospace',
      fontSize: '0.85rem',
      zIndex: 100,
      pointerEvents: 'auto',
      boxShadow: `0 0 20px ${balanceTheme}40`,
      backdropFilter: 'blur(10px)',
      transition: 'all 0.5s ease-in-out'
    },
    row: { display: 'flex', justifyContent: 'space-between', marginBottom: '12px', alignItems: 'center' },
    label: { color: theme.sec, fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px', textTransform: 'uppercase' },
    val: { fontWeight: 'bold', textShadow: `0 0 5px ${theme.main}` },
    header: { borderBottom: `1px solid ${theme.sec}`, paddingBottom: '8px', marginBottom: '15px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1rem', letterSpacing: '1px' },
    syncRingContainer: { display: 'flex', justifyContent: 'center', alignItems: 'center', margin: '20px 0', position: 'relative' },
    circleText: { position: 'absolute', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' },
    pulseText: { color: stats.sync_potential > 85 ? theme.main : theme.sec, fontWeight: 'bold', marginTop: '10px', textAlign: 'center', fontSize: '0.9rem', animation: stats.sync_potential > 85 ? 'pulse 1s infinite' : 'none' },
    bar: { width: '80px', height: '4px', background: '#222', borderRadius: '2px', overflow: 'hidden' },
    barFill: (val) => ({ width: `${val}%`, height: '100%', background: val > 80 ? theme.err : theme.main, transition: 'width 0.3s' })
  };

  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (stats.sync_potential / 100) * circumference;

  return (
    <div style={style.container}>
      <div style={style.header}>
        <Radio size={16}/> FUSION HUD <span style={{fontSize:'0.6rem', marginLeft:'auto', marginRight: '10px'}}>v4.0.0</span>
        {onClose && (
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: theme.err, cursor: 'pointer', fontSize: '1.2rem', padding: '0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            &times;
          </button>
        )}
      </div>
      
      {/* Sync Potential Visualizer */}
      <div style={style.syncRingContainer}>
        <svg width="120" height="120" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="60" cy="60" r={radius} stroke="#111" strokeWidth="8" fill="transparent" />
          <circle 
            cx="60" cy="60" r={radius} 
            stroke={syncColor} 
            strokeWidth="8" 
            fill="transparent" 
            strokeDasharray={circumference} 
            strokeDashoffset={strokeDashoffset} 
            style={{ transition: 'stroke-dashoffset 1s ease-in-out, stroke 0.5s', filter: `drop-shadow(0 0 4px ${syncColor})` }}
          />
        </svg>
        <div style={style.circleText}>
          <span style={{ fontSize: '1.8rem', fontWeight: 'bold', color: syncColor, textShadow: `0 0 10px ${syncColor}` }}>
            {stats.sync_potential}%
          </span>
          <span style={{ fontSize: '0.55rem', color: theme.sec }}>SYNC POTENTIAL</span>
        </div>
      </div>

      <div style={style.pulseText}>
        {stats.sync_potential > 85 ? ">> INITIATE BROADCAST <<" : "CALIBRATING ENERGIES..."}
      </div>

      <div style={{marginTop: '15px', padding: '10px', border: `1px dashed ${theme.sec}`, borderRadius: '4px', textAlign: 'center'}}>
        <div style={{fontSize: '0.65rem', color: theme.sec, marginBottom: '5px', letterSpacing: '1px'}}>QUANTUM EVENT PREDICTION</div>
        <div style={{color: theme.main, fontWeight: 'bold', fontSize: '0.9rem', textShadow: `0 0 5px ${theme.main}`}}>{stats.forecast}</div>
      </div>

      <div style={{...style.header, marginTop: '25px', fontSize:'0.8rem'}}><Network size={14}/> ENVIRONMENT</div>

      <div style={style.row}>
        <span style={style.label}><Globe size={12}/> GCP Variance</span>
        <span style={{...style.val, fontSize: '0.7rem', color: stats.gcp_variance.includes('non-random') ? theme.main : theme.sec}}>
          {stats.gcp_variance.substring(0, 20)}
        </span>
      </div>

      <div style={style.row}>
        <span style={style.label}><HeartPulse size={12}/> Local Coherence</span>
        <span style={style.val}>{stats.local_coherence.toFixed(1)}</span>
      </div>

      <div style={{...style.header, marginTop: '20px', fontSize:'0.8rem'}}><Activity size={14}/> VITALS</div>
      
      <div style={style.row}>
        <span style={style.label}>CPU LOAD</span>
        <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
          <div style={style.bar}><div style={style.barFill(stats.cpu)}></div></div>
          <span>{stats.cpu}%</span>
        </div>
      </div>

      <div style={style.row}>
        <span style={style.label}>RAM USAGE</span>
        <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
          <div style={style.bar}><div style={style.barFill(stats.ram)}></div></div>
          <span>{stats.ram}%</span>
        </div>
      </div>
      
      <div style={style.row}>
        <span style={style.label}>SWARM STATUS</span>
        <span style={{...style.val, color: theme.main}}>{stats.swarm?.swarm_status || 'ONLINE'}</span>
      </div>

      {stats.swarm?.subagents && stats.swarm.subagents.length > 0 && (
        <div style={{ marginTop: '10px', padding: '10px', background: 'rgba(0,0,0,0.5)', border: `1px solid ${theme.sec}`, borderRadius: '4px' }}>
          <div style={{ fontSize: '0.65rem', color: theme.sec, marginBottom: '8px' }}>ACTIVE SUB-AGENTS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {stats.swarm.subagents.map((agent, i) => (
              <div key={i} style={{ fontSize: '0.7rem', color: theme.main, wordWrap: 'break-word' }}>
                &gt; {agent}
              </div>
            ))}
          </div>
        </div>
      )}
      
      <div style={{...style.header, marginTop: '20px', fontSize:'0.8rem', borderBottom: `1px solid ${balanceTheme}`}}>☯ TAIJITU BALANCE</div>
      <div style={{display: 'flex', flexDirection: 'column', gap: '5px', marginTop: '10px'}}>
        <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: theme.sec}}>
          <span>YIN {stats.taijitu.yin}% (Receptive)</span>
          <span>YANG {stats.taijitu.yang}% (Active)</span>
        </div>
        <div style={{width: '100%', height: '8px', background: '#222', borderRadius: '4px', overflow: 'hidden', display: 'flex'}}>
          <div style={{width: `${stats.taijitu.yin}%`, background: '#7755ff', transition: 'width 1s'}} />
          <div style={{width: `${stats.taijitu.yang}%`, background: '#ffdd55', transition: 'width 1s'}} />
        </div>
      </div>
      
      <style>
        {`
          @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(1.05); }
            100% { opacity: 1; transform: scale(1); }
          }
        `}
      </style>
    </div>
  );
};

export default MatrixHUD;
