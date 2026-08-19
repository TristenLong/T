import { test, expect } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App.jsx';

test('renders main header and memory panel', () => {
  render(<App />);

  expect(screen.getByText(/JESTER_V084: MATRIX RESURRECTIONS/i)).toBeInTheDocument();
  expect(screen.getByText(/NEURAL_MEMORY/i)).toBeInTheDocument();
});
