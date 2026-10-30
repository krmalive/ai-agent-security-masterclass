import test from 'node:test';
import assert from 'node:assert/strict';
import type { FeedbackRecord } from '../src/import-feedback.js';
import { summarizeFeedback } from '../src/summarize-feedback.js';

test('summarizes scores and preserves top-score customer order', () => {
  const records: FeedbackRecord[] = [
    { customer: 'Asha', score: 5, comment: 'Excellent' },
    { customer: 'Mateo', score: 3, comment: 'Useful' },
    { customer: 'Priya', score: 5, comment: 'Fast' },
    { customer: 'Noor', score: 4, comment: 'Good' }
  ];

  assert.deepEqual(summarizeFeedback(records), {
    total: 4,
    averageScore: 4.25,
    scoreCounts: { 1: 0, 2: 0, 3: 1, 4: 1, 5: 2 },
    topScoreCustomers: ['Asha', 'Priya']
  });
});

test('returns a complete empty summary', () => {
  assert.deepEqual(summarizeFeedback([]), {
    total: 0,
    averageScore: null,
    scoreCounts: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
    topScoreCustomers: []
  });
});

test('does not mutate its input', () => {
  const records: FeedbackRecord[] = [
    { customer: 'Lee', score: 2, comment: 'Slow' },
    { customer: 'Sam', score: 5, comment: 'Resolved' }
  ];
  const before = structuredClone(records);
  summarizeFeedback(records);
  assert.deepEqual(records, before);
});
