// Hand-rolled SVG charts. No chart library, no inline styles (the CSP forbids
// them): colour comes from classes in style.css. Positions on the page are
// worked out here; the values themselves are printed as the bundle gave them.
import { s, nextId } from './dom.js';
import { fmtDay, fmtRange, raw } from './format.js';

function niceStep(span) {
  const pow = 10 ** Math.floor(Math.log10(span));
  const norm = span / pow;
  return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * pow;
}

function scale(values, fromZero) {
  let lo = fromZero ? 0 : Math.min(...values);
  let hi = Math.max(...values);
  if (hi === lo) hi = lo + Math.max(Math.abs(lo) * 0.05, 1);
  const step = niceStep((hi - lo) / 3);
  lo = fromZero ? 0 : Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  const ticks = [];
  for (let v = lo; v <= hi + step / 1000; v += step) ticks.push(v);
  return { lo, hi, ticks, decimals: Math.max(0, -Math.floor(Math.log10(step))) };
}

/** A weekly series as bars (cumulative totals) or a line with points
 *  (rate-like means). Partial weeks are drawn faded or hollow and, for lines,
 *  left unconnected. */
export function seriesChart(series) {
  const W = 320;
  const H = 136;
  const m = { l: 40, r: 8, t: 10, b: 22 };
  const pw = W - m.l - m.r;
  const ph = H - m.t - m.b;
  const pts = series.points;
  const n = pts.length;
  const bars = series.aggregation === 'weekly_total';
  const titleId = nextId('chart-title');
  const known = pts.filter((p) => p.value != null).map((p) => p.value);
  const svg = s('svg', {
    class: 'chart-svg', viewBox: `0 0 ${W} ${H}`, role: 'img',
    'aria-labelledby': titleId, focusable: 'false',
  });
  svg.append(s('title', { id: titleId }, `${series.label}, weekly. ${series.summary}`));
  if (!known.length) return svg;

  const sc = scale(known, bars);
  const y = (v) => m.t + ph - ((v - sc.lo) / (sc.hi - sc.lo)) * ph;
  const step = pw / n;
  const x = (i) => m.l + step * (i + 0.5);

  for (const t of sc.ticks) {
    svg.append(s('line', { class: 'gl', x1: m.l, x2: W - m.r, y1: y(t), y2: y(t) }));
    svg.append(s('text', { class: 'ax', x: m.l - 5, y: y(t) + 3, 'text-anchor': 'end' }, t.toFixed(sc.decimals)));
  }
  svg.append(s('text', { class: 'ax', x: m.l, y: H - 6, 'text-anchor': 'start' }, fmtDay(pts[0].start)));
  svg.append(s('text', { class: 'ax', x: W - m.r, y: H - 6, 'text-anchor': 'end' }, fmtDay(pts[n - 1].start)));

  const label = (p) => `${fmtRange(p.start, p.end)}: ${p.value == null ? 'no data'
    : `${raw(p.value)} ${series.unit}`} (${p.n_days} ${p.n_days === 1 ? 'day' : 'days'}${p.partial ? ', partial week' : ''})`;

  if (bars) {
    const bw = Math.max(2, step * 0.66);
    pts.forEach((p, i) => {
      if (p.value == null) return;
      const top = y(p.value);
      svg.append(s('rect', {
        class: p.partial ? 'bar partial' : 'bar',
        x: x(i) - bw / 2, y: top, width: bw, height: Math.max(1, m.t + ph - top), rx: 1.5,
      }, s('title', null, label(p))));
    });
  } else {
    let run = [];
    const flush = () => {
      if (run.length > 1) {
        svg.append(s('polyline', { class: 'line', points: run.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(' ') }));
      }
      run = [];
    };
    pts.forEach((p, i) => {
      if (p.value == null || p.partial) { flush(); return; }
      run.push([x(i), y(p.value)]);
    });
    flush();
    pts.forEach((p, i) => {
      if (p.value == null) return;
      svg.append(s('circle', {
        class: p.partial ? 'dot partial' : 'dot', cx: x(i), cy: y(p.value), r: p.partial ? 2.6 : 2,
      }, s('title', null, label(p))));
    });
  }
  return svg;
}

/** A tiny bar strip for a handful of values (used inside onboarding cards).
 *  Bar heights come from the raw values (geometry); every word and number in the
 *  tooltips and the accessible name comes from `labels`, the display strings Python
 *  wrote for those values. Without labels the strip says so rather than print raw. */
export function miniBars(values, labels) {
  const W = 120;
  const H = 34;
  const nums = values.filter((v) => v != null);
  const top = Math.max(...nums, 1);
  const bw = W / values.length;
  const named = Array.isArray(labels) && labels.length === values.length;
  const svg = s('svg', { class: 'mini-bars', viewBox: `0 0 ${W} ${H}`, role: 'img', focusable: 'false',
    'aria-label': named ? `Weekly values: ${labels.join(', ')}` : 'Weekly values not available' });
  values.forEach((v, i) => {
    if (v == null) return;
    const hgt = Math.max(1, (v / top) * (H - 2));
    svg.append(s('rect', { class: 'bar', x: i * bw + bw * 0.15, y: H - hgt, width: bw * 0.7, height: hgt, rx: 1.5 },
      named ? s('title', null, labels[i]) : null));
  });
  return svg;
}
