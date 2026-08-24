import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { MeshDistortMaterial, Icosahedron, TorusKnot } from '@react-three/drei';
import * as THREE from 'three';

const JesterBrain = ({ isSpeaking, isListening, isAnomaly }) => {
  const meshRef = useRef();
  const innerRef = useRef();
  
  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (meshRef.current) {
      meshRef.current.rotation.x = t * 0.2;
      meshRef.current.rotation.y = t * 0.3;
      
      // Pulse effect based on speaking/listening state
      const targetScale = isAnomaly ? 1.5 : (isSpeaking ? 1.4 : (isListening ? 1.1 : 1));
      meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
      
      // Glitch/Twitch effect
      if (Math.random() > (isAnomaly ? 0.90 : 0.98)) {
        meshRef.current.rotation.z += Math.random() * (isAnomaly ? 1.5 : 0.5);
      }
    }

    if (innerRef.current) {
        innerRef.current.rotation.x = -t * (isAnomaly ? 1.5 : 0.5);
        innerRef.current.rotation.y = -t * (isAnomaly ? 1.5 : 0.5);
        const innerScale = isAnomaly ? 0.9 : (isSpeaking ? 0.8 : 0.5);
        innerRef.current.scale.lerp(new THREE.Vector3(innerScale, innerScale, innerScale), 0.1);
    }
  });

  return (
    <group>
      <ambientLight intensity={0.2} />
      <pointLight position={[10, 10, 10]} intensity={1.5} color='#00FF41' />
      <pointLight position={[-10, -10, -10]} intensity={0.5} color='#008F11' />
      
      {/* Outer Shell - The Matrix Construct */}
      <Icosahedron ref={meshRef} args={[1, 1]}>
        <MeshDistortMaterial 
            color={isAnomaly ? '#FF003C' : (isSpeaking ? '#E0FFEB' : '#00FF41')} 
            speed={isAnomaly ? 8 : (isSpeaking ? 5 : 2)} 
            distort={isAnomaly ? 0.8 : 0.4} 
            radius={1} 
            wireframe={true} 
            emissive={isAnomaly ? '#440000' : '#002200'}
            emissiveIntensity={isAnomaly ? 1 : 0.5}
            transparent
            opacity={0.8}
        />
      </Icosahedron>

      {/* Inner Core - The Singularity */}
      <TorusKnot ref={innerRef} args={[0.6, 0.2, 100, 16]}>
        <meshStandardMaterial 
            color={isAnomaly ? '#FFD700' : (isSpeaking ? '#FFFFFF' : '#008F11')} 
            wireframe={true}
            emissive={isAnomaly ? '#FF3366' : '#00FF41'}
            emissiveIntensity={isAnomaly ? 3 : (isSpeaking ? 2 : 0.5)}
        />
      </TorusKnot>

      {/* Postprocessing removed due to R3F version crash */}
    </group>
  );
};

export default JesterBrain;
