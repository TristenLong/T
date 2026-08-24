# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: default\jester\jester.test.js >> Jester >> [UI-001] should complete jester workflow
- Location: .tdad\workflows\default\jester\jester.test.js:15:5

# Error details

```
Error: Test not implemented yet
```

# Test source

```ts
  1  | // TDAD fixtures provide automatic trace capture for Golden Packet
  2  | import { test, expect } from '../../../tdad-fixtures.js';
  3  | import { performJesterAction } from './jester.action.js';
  4  | 
  5  | /**
  6  |  * Test based on Gherkin specification:
  7  |  * Feature: Jester AI Core
  8  |  *   As a scientist
  9  |  *   I want a full self learning ai and problem solver
  10 |  *   So that I can detect anomalies and test science hypotheses
  11 |  * ...
  12 |  */
  13 | 
  14 | test.describe('Jester', () => {
  15 |     test('[UI-001] should complete jester workflow', async ({ page, tdadTrace }) => {
  16 |         // TODO: Implement test steps here
> 17 |         throw new Error('Test not implemented yet');
     |               ^ Error: Test not implemented yet
  18 |     });
  19 | });
  20 | 
```