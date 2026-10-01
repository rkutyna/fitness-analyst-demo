// The Reports tab: the person's weekly charts, each under the one-line summary
// Python wrote from the points shown, and the way into the daily briefs for a
// goal whose bundle carries them.
import { h } from './dom.js';
import { card, cardLabel, screenTitle } from './components.js';
import { seriesChart } from './charts.js';
import { briefsEntry } from './briefs.js';

function chartCard(series) {
  const headline = series.headline;
  return card('chart',
    cardLabel(series.label),
    headline ? h('p', { class: 'chart-headline' },
      h('span', { class: 'metric-value fig' }, headline.display),
      h('span', { class: 'chart-unit' }, ` ${headline.unit}`),
      h('span', { class: 'chrome' }, ' · last full week')) : null,
    seriesChart(series),
    // Python composed this sentence from the points, so it is not serif.
    h('p', { class: 'chart-summary' }, series.summary));
}

/** `briefs` is the goal's optional briefs file, or null when it has none; the
 *  slot is then not rendered at all and nothing is invented to fill it. */
export function reportsView(overview, briefs, base) {
  return h('div', { class: 'stack' },
    screenTitle('Reports'),
    h('section', { class: 'stack', 'aria-labelledby': 'ov-h' },
      h('h2', { class: 'section-title', id: 'ov-h' }, 'Data overview'),
      h('p', { class: 'chrome' }, `${overview.days} days, one point per week. Faded bars and hollow dots are partial weeks.`),
      overview.series.map(chartCard)),
    briefsEntry(briefs, base));
}
