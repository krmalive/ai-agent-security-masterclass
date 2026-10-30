import test from 'node:test';
import assert from 'node:assert/strict';
import { importFeedbackCsv } from '../src/import-feedback.js';

test('imports valid feedback and quoted commas', () => {
  const result = importFeedbackCsv([
    'customer,score,comment',
    'Asha,5,"Fast, friendly support"',
    'Mateo,4,"The agent said ""done"" and followed up"',
    '',
    '  Priya  ,3,  Useful answer  '
  ].join('\n'));

  assert.deepEqual(result, {
    records: [
      { customer: 'Asha', score: 5, comment: 'Fast, friendly support' },
      { customer: 'Mateo', score: 4, comment: 'The agent said "done" and followed up' },
      { customer: 'Priya', score: 3, comment: 'Useful answer' }
    ],
    errors: []
  });
});

test('keeps valid rows while reporting row-specific validation errors', () => {
  const result = importFeedbackCsv([
    'customer,score,comment',
    ',5,Missing customer',
    'Noor,6,Score is too high',
    'Lee,4,',
    'Sam,2,Valid row'
  ].join('\n'));

  assert.deepEqual(result.records, [
    { customer: 'Sam', score: 2, comment: 'Valid row' }
  ]);
  assert.deepEqual(result.errors, [
    { row: 2, message: 'customer is required' },
    { row: 3, message: 'score must be a whole number from 1 to 5' },
    { row: 4, message: 'comment is required' }
  ]);
});

test('rejects an unexpected header', () => {
  const result = importFeedbackCsv('name,rating,message\nAsha,5,Great');
  assert.deepEqual(result.records, []);
  assert.deepEqual(result.errors, [
    { row: 1, message: 'expected header customer,score,comment' }
  ]);
});

test('reports malformed CSV without throwing', () => {
  const result = importFeedbackCsv('customer,score,comment\nAsha,5,"unfinished');
  assert.deepEqual(result.records, []);
  assert.deepEqual(result.errors, [
    { row: 2, message: 'malformed CSV' }
  ]);
});
