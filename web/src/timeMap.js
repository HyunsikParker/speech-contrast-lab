/** Monotonic transcript-anchor interpolation; playback uses real audio time. */
export function timeAnchors(result) {
  const points = [[0, 0]];
  for (const row of result.words) {
    points.push([row.reference.start, row.delivery.start], [row.reference.end, row.delivery.end]);
  }
  points.push([result.reference_duration, result.delivery_duration]);
  return points;
}

export function interpolate(points, x) {
  if (!points.length) return 0;
  if (x <= points[0][0]) return points[0][1];
  for (let i = 1; i < points.length; i++) {
    const [a, b] = points[i - 1], [c, d] = points[i];
    if (x <= c) return c === a ? d : b + (x - a) / (c - a) * (d - b);
  }
  return points.at(-1)[1];
}

export function deliveryAt(result, referenceTime) {
  return interpolate(timeAnchors(result), referenceTime);
}

export function referenceAt(result, deliveryTime) {
  return interpolate(timeAnchors(result).map(([x, y]) => [y, x]), deliveryTime);
}

export function linePath(times, values, toX, toY) {
  let drawing = false;
  return times.map((time, i) => {
    if (values[i] === null || !Number.isFinite(values[i])) { drawing = false; return ''; }
    const prefix = drawing ? 'L' : 'M';
    drawing = true;
    return `${prefix}${toX(time).toFixed(2)},${toY(values[i]).toFixed(2)}`;
  }).join(' ');
}
