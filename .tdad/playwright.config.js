// @ts-check
// TDAD_WRAPPER_CONFIG_V2
// Stable wrapper that merges generated TDAD config with user overrides.
import { defineConfig } from '@playwright/test';
import generatedConfig from './playwright.generated.js';
import userConfig from './playwright.user.js';

function isPlainObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function deepMerge(base, override) {
  if (!isPlainObject(base)) {
    return isPlainObject(override) ? { ...override } : override;
  }
  if (!isPlainObject(override)) {
    return { ...base };
  }

  const merged = { ...base };
  for (const [key, overrideValue] of Object.entries(override)) {
    const baseValue = merged[key];
    if (isPlainObject(baseValue) && isPlainObject(overrideValue)) {
      merged[key] = deepMerge(baseValue, overrideValue);
    } else {
      merged[key] = overrideValue;
    }
  }
  return merged;
}

const mergedConfig = deepMerge(generatedConfig || {}, userConfig || {});

// Enforce TDAD-managed invariants.
mergedConfig.testDir = generatedConfig?.testDir || './workflows';
mergedConfig.globalSetup = generatedConfig?.globalSetup || './playwright-global-lock.cjs';

export default defineConfig(mergedConfig);
