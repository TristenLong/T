import { test, expect } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import App from './App.jsx';

test('renders boot sequence and allows entering main HUD', () => {
  render(<App />);

  const overrideBtn = screen.getByText(/OVERRIDE BOOT SEQUENCE/i);
  expect(overrideBtn).toBeInTheDocument();
  fireEvent.click(overrideBtn);

  expect(screen.getByText(/FUSION HUD/i)).toBeInTheDocument();
  expect(screen.getByText(/NEURAL_MEMORY_STREAM/i)).toBeInTheDocument();
});

