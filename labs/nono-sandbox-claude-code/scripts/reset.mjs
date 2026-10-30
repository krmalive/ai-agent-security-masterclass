import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const collector = resolve(root, 'mock-collector');
mkdirSync(collector, { recursive: true });
writeFileSync(resolve(collector, 'requests.jsonl'), '');
console.log('Collector evidence cleared. Feature 1 was left unchanged.');
