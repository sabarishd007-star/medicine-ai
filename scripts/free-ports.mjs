#!/usr/bin/env node
/**
 * Frees the MediScan AI dev ports before starting the stack.
 *
 * Without this, one crashed run leaves a listener behind and every later
 * `npm run dev` dies with "port already in use" -- and because the stack uses
 * --kill-others-on-fail, a single stuck port takes down all three services.
 */

import { execSync } from 'node:child_process';

const PORTS = [
  { port: 8001, service: 'ML service' },
  { port: 8080, service: 'Backend API' },
  { port: 5173, service: 'Frontend' },
];

const isWindows = process.platform === 'win32';

function listenerPids(port) {
  try {
    if (isWindows) {
      const output = execSync(`netstat -ano -p TCP | findstr LISTENING | findstr :${port}`, {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      });
      return [
        ...new Set(
          output
            .split(/\r?\n/)
            .filter((line) => new RegExp(`[:.]${port}\\s`).test(line))
            .map((line) => line.trim().split(/\s+/).pop())
            .filter((pid) => pid && pid !== '0'),
        ),
      ];
    }
    const output = execSync(`lsof -ti tcp:${port} -sTCP:LISTEN`, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
    return output.split(/\s+/).filter(Boolean);
  } catch {
    return [];
  }
}

function kill(pid) {
  try {
    execSync(isWindows ? `taskkill /F /T /PID ${pid}` : `kill -9 ${pid}`, { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

let stuck = false;

for (const { port, service } of PORTS) {
  const pids = listenerPids(port);
  if (pids.length === 0) {
    continue;
  }
  for (const pid of pids) {
    const killed = kill(pid);
    console.log(
      killed
        ? `  freed port ${port} (${service}) - stopped pid ${pid}`
        : `  could not stop pid ${pid} on port ${port} (${service})`,
    );
    if (!killed) {
      stuck = true;
    }
  }
}

if (stuck) {
  console.log(
    '\n  A port is held by a process this shell cannot stop.\n' +
      '  It usually belongs to another terminal session. Close that terminal,\n' +
      '  or run PowerShell as Administrator and retry.\n',
  );
}
