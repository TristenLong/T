import React, { useEffect, useRef } from 'react';

const MatrixRain = ({ color = '#0F0' }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    const chars = 'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    
    const createColumns = () => {
        const colWidth = 15;
        const numColumns = Math.ceil(width / colWidth);
        return Array(numColumns).fill(null).map((_, i) => ({
            x: i * colWidth,
            y: Math.random() * -100,
            speed: 0.5 + Math.random() * 1.5,
            size: Math.floor(10 + Math.random() * 14),
            opacity: 0.1 + Math.random() * 0.9,
            chars: [] 
        }));
    };

    let columns = createColumns();

    const draw = () => {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
      ctx.fillRect(0, 0, width, height);

      columns.forEach(col => {
        ctx.font = `${col.size}px monospace`;
        
        const text = chars[Math.floor(Math.random() * chars.length)];
        const isHead = Math.random() > 0.98;

        if (isHead) {
             ctx.fillStyle = '#FFF';
             ctx.shadowBlur = 10;
             ctx.shadowColor = color;
        } else {
             ctx.fillStyle = color; 
             ctx.globalAlpha = col.opacity;
             ctx.shadowBlur = 0;
        }

        ctx.fillText(text, col.x, col.y);
        ctx.globalAlpha = 1.0;

        if (col.y > height && Math.random() > 0.975) {
          col.y = -50;
          col.speed = 0.5 + Math.random() * 1.5;
          col.size = Math.floor(10 + Math.random() * 14);
          col.opacity = 0.1 + Math.random() * 0.9;
        }
        col.y += col.speed;
      });
      requestAnimationFrame(draw);
    };

    const animationId = requestAnimationFrame(draw);
    const handleResize = () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        columns = createColumns();
    };
    window.addEventListener('resize', handleResize);
    return () => {
        window.removeEventListener('resize', handleResize);
        cancelAnimationFrame(animationId);
    };
  }, [color]);

  return <canvas ref={canvasRef} style={{ position: 'fixed', top: 0, left: 0, zIndex: 0, opacity: 1, background: 'transparent', pointerEvents: 'none' }} />;
};

export default MatrixRain;