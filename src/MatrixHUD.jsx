import React, { useState, useEffect } from 'react';
import { Cpu, Zap, Activity, Thermometer } from 'lucide-react';

const MatrixHUD = ({ theme }) => {
  const [stats, setStats] = useState({ 
    miner: { hashrate: 'OFFLINE', algo: 'N/A', status: 'WAITING' },
    cpu: 0, ram: 0, ai_status: 'CHECKING' 
  });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch('/api/matrix_status');
        const data = await res.json();
        if (data) setStats(data);
      } catch (e) {
        // Silent fail
      }
    };
    const interval = setInterval(fetchStats, 2000);
    fetchStats();
    return () => clearInterval(interval);
  }, []);

  const style = {
    container: {
      position: 'absolute',
      top: '100px',
      right: '20px',
      width: '220px',
      background: 'rgba(0,10,0,0.85)',
      border: `1px solid ${theme.sec}`,
      borderRadius: '8px',
      padding: '15px',
      color: theme.main,
      fontFamily: 'monospace',
      fontSize: '0.8rem',
      zIndex: 20,
      pointerEvents: 'auto'
    },
    row: { display: 'flex', justifyContent: 'space-between', marginBottom: '8px', alignItems: 'center' },
    label: { color: theme.sec, fontSize: '0.7rem' },
    val: { fontWeight: 'bold' },
    header: { borderBottom: `1px solid ${theme.sec}`, paddingBottom: '5px', marginBottom: '10px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }
  };

  return (
    <div style={style.container}>
      <div style={style.header}><Zap size={14}/> QUANTUM MINER</div>
      
      <div style={style.row}>
        <span style={style.label}>STATUS</span>
        <span style={{...style.val, color: stats.miner.status === 'MINING' ? theme.main : theme.err}}>
          {stats.miner.status}
        </span>
      </div>
      
      <div style={style.row}>
        <span style={style.label}>HASHRATE</span>
        <span style={style.val}>{stats.miner.hashrate}</span>
      </div>
      
      <div style={style.row}>
        <span style={style.label}>ALGORITHM</span>
        <span style={style.val}>{stats.miner.algo || 'RandomX'}</span>
      </div>

      <div style={{...style.header, marginTop: '15px'}}><Activity size={14}/> SYSTEM VITALS</div>
      
      <div style={style.row}>
        <span style={style.label}>CPU LOAD</span>
        <div style={{display: 'flex', alignItems: 'center', gap: '5px'}}>
          <div style={{width: '60px', height: '4px', background: '#333'}}>
            <div style={{width: `${stats.cpu}%`, height: '100%', background: stats.cpu > 80 ? theme.err : theme.main}}></div>
          </div>
          {stats.cpu}%
        </div>
      </div>

      <div style={style.row}>
        <span style={style.label}>RAM USAGE</span>
        <span style={style.val}>{stats.ram}%</span>
      </div>
      
      <div style={style.row}>
        <span style={style.label}>AI CORE</span>
        <span style={style.val}>{stats.ai_status}</span>
      </div>

    </div>
  );
};

export default MatrixHUD;
