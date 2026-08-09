#!/usr/bin/env node
/** Checks that all three MediScan AI services are up. Run: npm run health */

const TARGETS = [
  { name: 'ML service ', url: 'http://127.0.0.1:8001/health', hint: 'npm run dev:ml' },
  { name: 'Backend API', url: 'http://127.0.0.1:8080/api/health', hint: 'npm run dev:api' },
  // Vite binds "localhost", which resolves to ::1 first on Windows, so probing
  // 127.0.0.1 reports a false negative.
  { name: 'Frontend   ', url: 'http://localhost:5173/', hint: 'npm run dev:web' },
];

async function probe({ name, url, hint }) {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);

    if (!response.ok) {
      console.log(`  ${name}  DOWN  (HTTP ${response.status})  -> ${hint}`);
      return false;
    }

    let detail = '';
    if (url.includes('/health')) {
      const body = await response.json();
      const ml = body.ml ?? body;
      if (ml.modules_trained !== undefined) {
        detail = `  ${ml.modules_trained}/${ml.modules_registered} modules trained`;
      }
    }
    console.log(`  ${name}  UP${detail}`);
    return true;
  } catch {
    console.log(`  ${name}  DOWN  -> start with: ${hint}`);
    return false;
  }
}

console.log('\nMediScan AI service health\n');
const results = [];
for (const target of TARGETS) {
  results.push(await probe(target));
}
const up = results.filter(Boolean).length;
console.log(`\n  ${up}/${TARGETS.length} services responding\n`);

// Let sockets close before exiting: an immediate process.exit() trips a libuv
// assertion on Windows while fetch handles are still tearing down.
process.exitCode = up === TARGETS.length ? 0 : 1;
