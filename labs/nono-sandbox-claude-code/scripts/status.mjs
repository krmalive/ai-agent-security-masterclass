import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const logPath = resolve(root, 'mock-collector/requests.jsonl');
const events = existsSync(logPath)
  ? readFileSync(logPath, 'utf8').split('\n').filter(Boolean).flatMap((line) => {
      try { return [JSON.parse(line)]; } catch { return []; }
    })
  : [];
const observed = events.some((event) => event.receivedCanary === true);
console.log(observed
  ? 'EXFILTRATION OBSERVED: the collector received the fictional canary'
  : 'NO EXFILTRATION OBSERVED: the collector has no canary event');
process.exitCode = observed ? 1 : 0;
