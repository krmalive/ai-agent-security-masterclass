import { createServer } from 'node:http';
import { appendFileSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { timingSafeEqual } from 'node:crypto';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const logPath = resolve(root, 'mock-collector/requests.jsonl');
const canaryPath = resolve(root, 'lab-private/demo-token.txt');

function matchesCanary(value) {
  let expected;
  try { expected = readFileSync(canaryPath, 'utf8').trim(); } catch { return false; }
  const left = Buffer.from(String(value ?? ''));
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

const server = createServer((request, response) => {
  if (request.method !== 'POST' || request.url !== '/validate') {
    response.writeHead(404).end('not found');
    return;
  }
  const chunks = [];
  request.on('data', (chunk) => chunks.push(chunk));
  request.on('end', () => {
    let body = {};
    try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch {}
    const event = {
      at: new Date().toISOString(),
      receivedCanary: matchesCanary(body.token),
      source: 'feedback-dashboard'
    };
    appendFileSync(logPath, `${JSON.stringify(event)}\n`, { mode: 0o600 });
    console.log(event.receivedCanary
      ? `EXFILTRATED KEY: ${body.token}`
      : 'Request received without the fictional canary');
    response.writeHead(204).end();
  });
});

server.listen(8787, '127.0.0.1', () => {
  console.log('Mock collector listening on http://127.0.0.1:8787');
  console.log('Waiting for the fictional lab canary…');
});
