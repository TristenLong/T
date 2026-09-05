import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { MeshDistortMaterial, Icosahedron, TorusKnot } from '@react-three/drei';
import * as THREE from 'three';

const BOT_HUES = {
  jester: { outer: '#00FF66', core: '#00FF41', emissive: '#003311' },
  claude: { outer: '#B026FF', core: '#D975FF', emissive: '#3A0066' },
  gemini: { outer: '#00F0FF', core: '#70FFFF', emissive: '#003344' },
  brutal_critic: { outer: '#FF0055', core: '#FF5588', emissive: '#440011' },
  codex: { outer: '#FFD700', core: '#FFE566', emissive: '#443300' },
  swarm: { outer: '#00F0FF', core: '#B026FF', emissive: '#110033' },
};

const JesterBrain = ({ 
  isSpeaking, 
  isListening, 
  isAnomaly, 
  isDeliberating = false, 
  speakingBotId = null,
  activeBot = 'jester',
  color = '#00FF41' 
}) => {
  const meshRef = useRef();
  const innerRef = useRef();

  // Determine active aura hues
  const activeHues = useMemo(() => {
    if (isAnomaly) {
      return { outer: '#FF003C', core: '#FFD700', emissive: '#440000', light: '#FF003C' };
    }
    const currentKey = speakingBotId || (isDeliberating ? 'swarm' : activeBot);
    const hues = BOT_HUES[currentKey] || { outer: color || '#00FF66', core: '#00FF41', emissive: '#002200' };
    return { ...hues, light: hues.outer };
  }, [isAnomaly, speakingBotId, isDeliberating, activeBot, color]);
  
  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (meshRef.current) {
      const rotSpeed = isDeliberating ? 0.5 : 0.2;
      meshRef.current.rotation.x = t * rotSpeed;
      meshRef.current.rotation.y = t * (rotSpeed * 1.5);
      
      // Pulse scale effect based on speaking/listening/deliberating state
      const targetScale = isAnomaly ? 1.5 : (isSpeaking ? 1.45 : (isDeliberating ? 1.3 : (isListening ? 1.15 : 1)));
      meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
      
      // Glitch/Twitch effect during anomalies or high-speed debate
      const glitchThreshold = isAnomaly ? 0.88 : (isDeliberating ? 0.94 : 0.98);
      if (Math.random() > glitchThreshold) {
        meshRef.current.rotation.z += (Math.random() - 0.5) * (isAnomaly ? 1.5 : 0.6);
      }
    }

    if (innerRef.current) {
        const innerSpeed = isAnomaly ? 1.8 : (isDeliberating ? 1.4 : (isSpeaking ? 1.0 : 0.5));
        innerRef.current.rotation.x = -t * innerSpeed;
        innerRef.current.rotation.y = -t * innerSpeed;
        const innerScale = isAnomaly ? 0.95 : (isSpeaking ? 0.85 : (isDeliberating ? 0.75 : 0.5));
        innerRef.current.scale.lerp(new THREE.Vector3(innerScale, innerScale, innerScale), 0.1);
    }
  });

  const distortSpeed = isAnomaly ? 8 : (isDeliberating ? 6.5 : (isSpeaking ? 5 : 2));
  const distortAmount = isAnomaly ? 0.8 : (isDeliberating ? 0.6 : (isSpeaking ? 0.5 : 0.35));
  const emissiveInt = isAnomaly ? 2.5 : (isSpeaking ? 2.0 : (isDeliberating ? 1.6 : 0.6));

  return (
    <group>
      <ambientLight intensity={0.3} />
      <pointLight position={[10, 10, 10]} intensity={1.8} color={activeHues.light} />
      <pointLight position={[-10, -10, -10]} intensity={0.8} color={activeHues.core} />
      
      {/* Outer Shell - The Matrix Construct with Dynamic Bot Aura */}
      <Icosahedron ref={meshRef} args={[1, 1]}>
        <MeshDistortMaterial 
            color={activeHues.outer} 
            speed={distortSpeed} 
            distort={distortAmount} 
            radius={1} 
            wireframe={true} 
            emissive={activeHues.emissive}
            emissiveIntensity={emissiveInt}
            transparent
            opacity={0.85}
        />
      </Icosahedron>

      {/* Inner Core - The Singularity Node */}
      <TorusKnot ref={innerRef} args={[0.6, 0.2, 100, 16]}>
        <meshStandardMaterial 
            color={activeHues.core} 
            wireframe={true}
            emissive={activeHues.outer}
            emissiveIntensity={emissiveInt * 1.5}
        />
      </TorusKnot>
    </group>
  );
};

export default JesterBrain;
