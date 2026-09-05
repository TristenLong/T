import { test, expect, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import App from './App.jsx';

afterEach(() => {
  cleanup();
});

test('renders boot sequence and allows entering main HUD', () => {
  render(<App />);

  const overrideBtn = screen.getByText(/OVERRIDE BOOT SEQUENCE/i);
  expect(overrideBtn).toBeInTheDocument();
  fireEvent.click(overrideBtn);

  expect(screen.getByText(/FUSION HUD/i)).toBeInTheDocument();
  expect(screen.getByText(/NEURAL_MEMORY_STREAM/i)).toBeInTheDocument();
});

test('renders all 5 separate bots and confirm comms action in chat interface', () => {
  render(<App />);

  const overrideBtn = screen.getByText(/OVERRIDE BOOT SEQUENCE/i);
  fireEvent.click(overrideBtn);

  // Verify all fleet bot buttons are present
  expect(screen.getByRole('button', { name: /SWARM ROUNDTABLE/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /CLAUDE CODE/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /GEMINI SCOUT/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /BRUTAL CRITIC/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /CODEX/i })).toBeInTheDocument();

  // Verify Confirm Comms button
  const confirmBtn = screen.getByRole('button', { name: /CONFIRM COMMS/i });
  expect(confirmBtn).toBeInTheDocument();

  // Switch to an individual specialist bot
  const criticBtn = screen.getByRole('button', { name: /BRUTAL CRITIC/i });
  fireEvent.click(criticBtn);
  expect(screen.getByText(/DIRECT LINK: BRUTAL CRITIC/i)).toBeInTheDocument();

  // Verify voice preview and specialist action buttons are present and clickable
  const voiceBtn = screen.getByRole('button', { name: /VOICE PREVIEW/i });
  expect(voiceBtn).toBeInTheDocument();
  fireEvent.click(voiceBtn);

  const auditBtn = screen.getByRole('button', { name: /3-LENS AUDIT/i });
  expect(auditBtn).toBeInTheDocument();
  fireEvent.click(auditBtn);
});

test('renders Sentry Watcher toggle, RAM purge button, and Swarm Execute Consensus button', () => {
  render(<App />);

  const overrideBtn = screen.getByText(/OVERRIDE BOOT SEQUENCE/i);
  fireEvent.click(overrideBtn);

  // Sentry toggle button and Auto-Heal button
  const sentryBtn = screen.getByRole('button', { name: /SENTRY:/i });
  expect(sentryBtn).toBeInTheDocument();
  
  const autoHealBtn = screen.getByRole('button', { name: /AUTO-HEAL:/i });
  expect(autoHealBtn).toBeInTheDocument();
  fireEvent.click(autoHealBtn);

  // RAM purge button
  expect(screen.getByText(/PURGE/i)).toBeInTheDocument();

  // Execute consensus and Run Full Pipeline buttons
  const execBtn = screen.getByRole('button', { name: /EXECUTE CONSENSUS/i });
  expect(execBtn).toBeInTheDocument();
  fireEvent.click(execBtn);

  const pipelineBtn = screen.getByRole('button', { name: /RUN FULL PIPELINE/i });
  expect(pipelineBtn).toBeInTheDocument();
  fireEvent.click(pipelineBtn);
});



