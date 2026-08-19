import React from 'react';
import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

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
