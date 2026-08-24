import React from 'react';
import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Mock Web Speech API
globalThis.SpeechSynthesisUtterance = vi.fn().mockImplementation((text) => ({
  text,
  pitch: 1,
  rate: 1,
  onstart: null,
  onend: null,
}));

globalThis.speechSynthesis = {
  speak: vi.fn((ut) => {
    if (ut && typeof ut.onend === 'function') ut.onend();
  }),
  cancel: vi.fn(),
  pause: vi.fn(),
  resume: vi.fn(),
};

// Mock fetch API
globalThis.fetch = vi.fn().mockResolvedValue({
  json: vi.fn().mockResolvedValue({
    cpu: 10,
    ram: 45,
    status: 'ONLINE',
    model: 'gemini-3.1-pro',
    logic_core: 'ONLINE',
    swarm: { swarm_status: 'ACTIVE', subagents: ['Architect', 'Navigator', 'ComputerUse'], status: 'SINGULARITY_ONLINE' },
    error: null
  }),
  body: {
    getReader: vi.fn().mockReturnValue({
      read: vi.fn().mockResolvedValue({ done: true, value: new Uint8Array() })
    })
  }
});

// Mock three.js-related React components for jsdom tests
vi.mock('@react-three/fiber', () => {
  return {
    Canvas: ({ children }) => <div data-testid="mock-canvas">{children}</div>,
    useFrame: () => {},
  };
});

vi.mock('@react-three/drei', () => {
  return {
    PerspectiveCamera: ({ children }) => <div data-testid="mock-camera">{children}</div>,
    Stars: () => <div data-testid="mock-stars" />,
    MeshDistortMaterial: (props) => <meshDistortMaterial {...props} />,
    Icosahedron: ({ children }) => <div data-testid="mock-icosahedron">{children}</div>,
    TorusKnot: ({ children }) => <div data-testid="mock-torus-knot">{children}</div>,
  };
});
