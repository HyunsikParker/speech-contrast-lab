import { test } from 'node:test';
import assert from 'node:assert/strict';
import { deliveryAt, referenceAt, linePath } from '../src/timeMap.js';

const result = { reference_duration: 3, delivery_duration: 4, words: [
  { reference: { start: 0.2, end: 1 }, delivery: { start: 0.3, end: 1.5 } },
  { reference: { start: 1.4, end: 2.8 }, delivery: { start: 2, end: 3.7 } },
] };

test('seek conversion preserves real word anchors in both directions', () => {
  assert.equal(deliveryAt(result, 1.4), 2);
  assert.equal(referenceAt(result, 3.7), 2.8);
  for (const t of [0, 0.1, 0.7, 1.2, 2, 3]) assert.ok(Math.abs(referenceAt(result, deliveryAt(result, t)) - t) < 1e-9);
});
test('unvoiced pitch gaps are not connected into invented contours', () => {
  assert.equal(linePath([0, 1, 2, 3], [2, null, 4, 5], x => x, y => y), 'M0.00,2.00  M2.00,4.00 L3.00,5.00');
});
