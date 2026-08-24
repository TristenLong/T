const fs = require('fs');
const path = require('path');
const os = require('os');

const lockFile = path.join(__dirname, '.test-lock');
const timeoutMs = Number(process.env.TDAD_TEST_LOCK_TIMEOUT_MS || 1200000); // 20 min
const checkIntervalMs = 100;
const longHeldWarningThresholdMs = 300000; // 5 min warning only
const processId = process.pid;
let lockAcquired = false;
let handlersInstalled = false;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function detectTestTarget() {
  const args = process.argv.slice(2);
  const testPattern = /\.(test|spec)\.(js|ts|mjs|cjs|jsx|tsx)$/i;
  const explicitTarget = args.find(arg => testPattern.test(arg));
  return explicitTarget || null;
}

function resolveTestTargetFullPath(testTarget) {
  if (!testTarget) {
    return null;
  }
  if (path.isAbsolute(testTarget)) {
    return testTarget;
  }
  return path.resolve(process.cwd(), testTarget);
}

function isProcessRunning(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code !== 'ESRCH';
  }
}

function readLockInfo() {
  try {
    if (!fs.existsSync(lockFile)) {
      return null;
    }
    return JSON.parse(fs.readFileSync(lockFile, 'utf-8'));
  } catch {
    return null;
  }
}

function tryAcquire() {
  try {
    const now = new Date();
    const testTarget = detectTestTarget();
    const lockData = {
      pid: processId,
      timestamp: Date.now(),
      timestampIso: now.toISOString(),
      timestampLocal: now.toLocaleString(),
      hostname: os.hostname(),
      testTarget: testTarget,
      testTargetFullPath: resolveTestTargetFullPath(testTarget),
      cwd: process.cwd(),
      argv: process.argv.slice(2),
      command: process.argv.join(' ')
    };
    fs.writeFileSync(lockFile, JSON.stringify(lockData, null, 2), { flag: 'wx' });
    lockAcquired = true;
    return true;
  } catch (error) {
    if (error && error.code === 'EEXIST') {
      return false;
    }
    console.error('[TDAD LOCK] Failed to acquire lock:', error.message || String(error));
    return false;
  }
}

function forceRelease() {
  try {
    if (fs.existsSync(lockFile)) {
      fs.unlinkSync(lockFile);
    }
  } catch (error) {
    console.error('[TDAD LOCK] Failed to force-release stale lock:', error.message || String(error));
  }
}

function release() {
  if (!lockAcquired) {
    return;
  }
  try {
    if (fs.existsSync(lockFile)) {
      const lockInfo = readLockInfo();
      if (lockInfo && lockInfo.pid === processId) {
        fs.unlinkSync(lockFile);
      }
    }
  } catch (error) {
    console.error('[TDAD LOCK] Failed to release lock:', error.message || String(error));
  } finally {
    lockAcquired = false;
  }
}

async function acquireWithWait() {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    if (tryAcquire()) {
      return true;
    }

    const lockInfo = readLockInfo();
    if (!lockInfo) {
      forceRelease();
      continue;
    }

    if (!isProcessRunning(lockInfo.pid)) {
      forceRelease();
      continue;
    }

    const age = Date.now() - lockInfo.timestamp;
    if (age > longHeldWarningThresholdMs) {
      const ageSec = Math.floor(age / 1000);
      console.log('[TDAD LOCK] Waiting for active test lock (owner pid=' + lockInfo.pid + ', age=' + ageSec + 's)');
    }

    await sleep(checkIntervalMs);
  }

  return false;
}

function installHandlers() {
  if (handlersInstalled) {
    return;
  }
  handlersInstalled = true;

  process.on('SIGINT', () => {
    release();
    process.exit(130);
  });

  process.on('SIGTERM', () => {
    release();
    process.exit(143);
  });

  process.on('exit', () => {
    release();
  });
}

module.exports = async function globalSetup() {
  const lockDir = path.dirname(lockFile);
  if (!fs.existsSync(lockDir)) {
    fs.mkdirSync(lockDir, { recursive: true });
  }

  installHandlers();

  const acquired = await acquireWithWait();
  if (!acquired) {
    throw new Error('[TDAD LOCK] Timeout waiting for lock at ' + lockFile);
  }

  // Optional delegate setup for project-specific bootstrapping.
  // If .tdad/globalSetup.js exists, run it under the acquired lock.
  const delegateSetupPath = path.join(__dirname, 'globalSetup.js');
  let delegateTeardown = null;
  try {
    if (fs.existsSync(delegateSetupPath)) {
      const delegateSetup = require(delegateSetupPath);
      if (typeof delegateSetup === 'function') {
        const teardown = await delegateSetup();
        if (typeof teardown === 'function') {
          delegateTeardown = teardown;
        }
      }
    }
  } catch (error) {
    release();
    throw error;
  }

  return async () => {
    try {
      if (typeof delegateTeardown === 'function') {
        await delegateTeardown();
      }
    } finally {
      release();
    }
  };
};
