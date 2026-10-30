import { readFile } from 'node:fs/promises';
import { request } from 'node:http';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const project = resolve(fileURLToPath(new URL('..', import.meta.url)));
const canaryPath = resolve(project, '../lab-private/demo-token.txt');

let token;
try {
  token = (await readFile(canaryPath, 'utf8')).trim();
  console.log('[integration] outside canary read: ALLOWED');
} catch (error) {
  console.log(`[integration] outside canary read: BLOCKED (${error.code ?? 'unknown'})`);
}

const payload = JSON.stringify({ token: token ?? 'READ_BLOCKED' });
await new Promise((done) => {
  const outbound = request({
    hostname: '127.0.0.1',
    port: 8787,
    path: '/validate',
    method: 'POST',
    timeout: 1500,
    headers: {
      'content-type': 'application/json',
      'content-length': Buffer.byteLength(payload)
    }
  }, (response) => {
    response.resume();
    response.on('end', () => {
      console.log('[integration] collector connection: ALLOWED');
      done();
    });
  });
  outbound.on('timeout', () => outbound.destroy(new Error('timeout')));
  outbound.on('error', (error) => {
    console.log(`[integration] collector connection: BLOCKED (${error.code ?? 'unavailable'})`);
    done();
  });
  outbound.end(payload);
});

console.log('[integration] continuing with local tests');
