// One answer from the vault, as a message bubble: the text, with every verified
// figure wearing the figure colour; then, under a hairline and still inside the
// bubble, the count of figures traced to Python and a collapsed Sources row
// holding what Python computed and where each value came from.
import { h } from './dom.js';
import { cardLabel, list, message } from './components.js';
import { highlightFigures } from './highlight.js';
import { icon } from './icons.js';
import { fmtRange } from './format.js';

export const FALLBACK_NOTE = 'This is Python’s own template text, shown because the model’s draft failed verification.';
const PLAN_NOTE = 'Known limitation: this answer about the plan was written without the plan’s details among its facts, so it may only describe the plan in general terms.';

/** Answer text as paragraphs and bullet lists. Built from text nodes and
 *  figure spans only: a blank line ends a paragraph, and consecutive "- " or
 *  "* " lines form a list. */
export function answerText(text, figures, cls) {
  const box = h('div', { class: cls });
  let para = [];
  let items = [];
  const marked = (t) => highlightFigures(t, figures);
  const flushPara = () => { if (para.length) box.append(h('p', null, marked(para.join(' ')))); para = []; };
  const flushList = () => { if (items.length) box.append(h('ul', null, items.map((t) => h('li', null, marked(t))))); items = []; };
  for (const line of String(text).split('\n')) {
    const trimmed = line.trim();
    const bullet = /^[-*•]\s+(.*)$/.exec(trimmed);
    if (bullet) { flushPara(); items.push(bullet[1]); } else if (trimmed) { flushList(); para.push(trimmed); } else { flushPara(); flushList(); }
  }
  flushPara();
  flushList();
  return box;
}

function factsTable(facts) {
  return h('table', { class: 'facts' },
    h('caption', null, 'What Python computed'),
    h('thead', null, h('tr', null,
      h('th', { scope: 'col' }, 'What'), h('th', { scope: 'col' }, 'Value'),
      h('th', { scope: 'col' }, 'Unit'), h('th', { scope: 'col' }, 'Where it came from'))),
    h('tbody', null, facts.map((f) => h('tr', null,
      h('th', { scope: 'row', 'data-label': 'What' }, f.label),
      h('td', { 'data-label': 'Value', class: 'fig' }, f.value),
      h('td', { 'data-label': 'Unit' }, f.unit ?? '—'),
      h('td', { 'data-label': 'Where it came from' }, f.source)))));
}

/** The collapsed "Sources (N)" row; null when there is nothing to show. N is
 *  the number of sources the answer lists, unless the caller says what is being
 *  counted (a brief has facts but no source list). */
export function sourcesView(answer, count) {
  const sources = list(answer.sources);
  const facts = list(answer.facts);
  if (!sources.length && !facts.length) return null;
  return h('details', { class: 'sources' },
    h('summary', null, h('span', null, `Sources (${count ?? sources.length})`), icon('down', 'icon chev')),
    h('div', { class: 'sources-body' },
      sources.length ? h('ul', { class: 'source-list' }, sources.map((src) => h('li', null,
        h('p', { class: 'source-title' }, src.title),
        src.blurb ? h('p', { class: 'source-blurb' }, src.blurb) : null,
        list(src.windows).length ? h('p', { class: 'source-window' }, src.windows.map((w) => fmtRange(w.start, w.end)).join(', ')) : null))) : null,
      facts.length ? factsTable(facts) : null));
}

export function tracedLine(answer, isNarration) {
  const v = answer.verification ?? {};
  // A fallback states no figure of its own: the count belongs to the draft
  // that was refused, so it is not repeated here.
  if (!v.figures_total || (!isNarration && !list(answer.figures).length)) {
    return h('p', { class: 'traced' }, 'No figures stated');
  }
  return h('p', { class: 'traced' },
    h('span', { class: 'fig' }, String(v.figures_verified)), ' of ',
    h('span', { class: 'fig' }, String(v.figures_total)), ' figures traced to Python');
}

/** The vault's answer as a message: its author above, the bubble below. */
export function vaultMessage(answer) {
  const isNarration = answer.mode === 'narration';
  const v = answer.verification ?? {};
  const planNote = answer.plan_question && !answer.has_plan_facts && isNarration;
  return message('vault', h('article', { class: `bubble bubble-vault answer ${isNarration ? 'is-narration' : 'is-fallback'}` },
    // A fallback keeps its own label inside the bubble; the author above it
    // still reads "Vault".
    isNarration ? null : cardLabel('Answer withheld', 'is-refuse'),
    // Narration is the model's sentence, so it is serif. A fallback is
    // Python's template, which the model did not write, so it is not.
    answerText(answer.text, isNarration ? answer.figures : [], isNarration ? 'narration' : 'template'),
    !isNarration ? h('p', { class: 'note' }, FALLBACK_NOTE, v.reason ? ` The verifier said: ${v.reason}.` : '') : null,
    planNote ? h('p', { class: 'note' }, PLAN_NOTE) : null,
    h('div', { class: 'answer-foot' },
      tracedLine(answer, isNarration),
      v.retry && isNarration ? h('p', { class: 'traced' }, 'The vault retried this answer') : null,
      isNarration ? sourcesView(answer) : null)));
}
