import React from 'react';

const JesterAvatar = ({ speaking, waving }) => {
  const styles = {
    root: {
      position: 'relative',
      width: '256px',
      height: '256px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    },
    base: {
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      border: '4px solid #00FF00',
      borderRadius: '50%',
      opacity: 0.5,
      animation: 'pulse 2s infinite'
    },
    innerCircle: {
      position: 'absolute',
      top: '8px',
      left: '8px',
      right: '8px',
      bottom: '8px',
      border: '2px solid #33FF33',
      borderRadius: '50%',
      opacity: 0.3,
      animation: 'spin 10s linear infinite'
    },
    face: {
      position: 'relative',
      zIndex: 10,
      width: '160px',
      height: '160px',
      backgroundColor: 'black',
      border: '1px solid #00FF00',
      borderRadius: '8px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 0 20px #00FF00'
    },
    eyes: {
      display: 'flex',
      gap: '16px',
      marginBottom: '16px'
    },
    eye: {
      width: '32px',
      height: '8px',
      backgroundColor: '#00FF00'
    },
    mouth: {
      display: 'flex',
      alignItems: 'flex-end',
      gap: '4px',
      height: '32px'
    },
    mouthBar: (speaking) => ({
      width: '8px',
      backgroundColor: '#33FF33',
      transition: 'all 0.1s',
      height: speaking ? '100%' : '4px',
      animation: speaking ? 'pulse 0.5s infinite' : 'none'
    }),
    hand: (waving) => ({
      position: 'absolute',
      right: '-40px',
      top: '40px',
      fontSize: '64px',
      transition: 'transform 0.5s',
      opacity: waving ? 1 : 0,
      transformOrigin: 'bottom left',
      animation: waving ? 'wave 1s infinite' : 'none'
    })
  };

  return (
    <div style={styles.root}>
      <div style={styles.base}></div>
      <div style={styles.innerCircle}></div>

      <div style={styles.face}>
        <div style={styles.eyes}>
          <div style={{...styles.eye, animation: speaking ? 'bounce 0.5s infinite' : 'none'}}></div>
          <div style={{...styles.eye, animation: speaking ? 'bounce 0.5s infinite' : 'none'}}></div>
        </div>

        <div style={styles.mouth}>
          {[...Array(5)].map((_, i) => (
            <div key={i} style={styles.mouthBar(speaking)}></div>
          ))}
        </div>
      </div>

      <div style={styles.hand(waving)}>
        👋
      </div>

      <style>{`
        @keyframes wave {
          0% { transform: rotate(0deg); }
          25% { transform: rotate(-20deg); }
          75% { transform: rotate(20deg); }
          100% { transform: rotate(0deg); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0% { opacity: 0.3; }
          50% { opacity: 0.6; }
          100% { opacity: 0.3; }
        }
        @keyframes bounce {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-4px); }
        }
      `}</style>
    </div>
  );
};

export default JesterAvatar;
