// The About page and the pipeline diagram (also shown in the side panel). The
// diagram is inline SVG built from constants; it carries no style attributes.
import { h, s, nextId } from './dom.js';
import { fmtTimestamp, fmtDay } from './format.js';

const NODES = [
  ['py', 'Synthetic vault', 'Simulated health data, 180 days per person'],
  ['py', 'Deterministic analysis', 'Python computes series, trends and plans'],
  ['py', 'Fact set', 'The only numbers the model may use'],
  ['llm', 'LLM narration', 'Turns the facts into sentences'],
  ['py', 'Verification gate', 'Unmatched figure: Python’s template is shown'],
  ['py', 'Frozen bundle', 'Reviewed JSON, generated in advance'],
  ['out', 'This site', 'Read-only. No model runs when you click'],
];

export function pipelineDiagram() {
  const W = 360;
  const boxH = 54;
  const gap = 26;
  const H = NODES.length * boxH + (NODES.length - 1) * gap + 8;
  const titleId = nextId('pl-t');
  const descId = nextId('pl-d');
  const svg = s('svg', { class: 'pipeline', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-labelledby': `${titleId} ${descId}` },
    s('title', { id: titleId }, 'The pipeline'),
    s('desc', { id: descId }, `${NODES.map(([, t]) => t).join(', then ')}.`));
  NODES.forEach(([kind, title, sub], i) => {
    const y = 4 + i * (boxH + gap);
    svg.append(
      s('rect', { class: `dg-${kind}`, x: 20, y, width: W - 40, height: boxH, rx: 10 }),
      s('text', { class: `dg-title dg-t-${kind}`, x: W / 2, y: y + 23, 'text-anchor': 'middle' }, title),
      s('text', { class: `dg-sub dg-t-${kind}`, x: W / 2, y: y + 40, 'text-anchor': 'middle' }, sub));
    if (i < NODES.length - 1) {
      const y1 = y + boxH;
      svg.append(
        s('line', { class: 'dg-arrow', x1: W / 2, y1: y1 + 2, x2: W / 2, y2: y1 + gap - 7 }),
        s('path', { class: 'dg-head', d: `M${W / 2 - 5} ${y1 + gap - 9} L${W / 2} ${y1 + gap - 2} L${W / 2 + 5} ${y1 + gap - 9} Z` }));
    }
  });
  return h('div', { class: 'diagram-wrap' }, svg,
    h('p', { class: 'diagram-key' }, h('span', { class: 'sw sw-py' }), 'Deterministic Python ', h('span', { class: 'sw sw-llm' }), 'Language model ', h('span', { class: 'sw sw-out' }), 'This site'));
}

function kv(rows) {
  return h('dl', { class: 'kv about-kv' }, rows.filter(Boolean).map(([k, v]) => h('div', { class: 'kv-row' }, h('dt', null, k), h('dd', null, v))));
}

export function aboutView(manifest) {
  const m = manifest.model;
  const providers = [m.providers, m.plan_providers].filter(Boolean);
  const unique = [...new Set(providers)];
  return h('div', { class: 'prose' },
    h('h1', { class: 'large-title', tabindex: '-1', 'data-focus': true }, 'How this demo works'),
    h('p', { class: 'lead' }, 'The rule the whole design turns on: ', h('strong', null, 'Python owns the truth; the model is only ever a text transformer.'),
      ' Every number a user sees is computed by deterministic Python from their health data. The language model is handed those numbers and asked to say them in plain words. It never derives one.'),
    manifest.dry_run ? null : h('h2', null, 'Who wrote what'),
    manifest.dry_run ? null : h('p', null, 'The answers on this site were generated in advance by a language model, ',
      h('strong', null, m.model),
      m.plan_model !== m.model ? [' (with ', h('strong', null, m.plan_model), ' writing the plans)'] : null,
      `, on ${fmtTimestamp(manifest.generated_at)}. Every figure in them was computed by Python from the synthetic data, and each answer was verified before publishing: a number in the text that Python did not compute fails that check. `,
      'An answer marked ', h('span', { class: 'inline-label' }, 'Answer withheld'),
      ' is a fallback: Python’s own template text, shown because the model’s draft failed verification. Nothing here is written or changed when you visit.'),
    manifest.dry_run ? h('p', { class: 'note' }, 'This build was generated with stub models, so the wording you see is placeholder text. The numbers, charts and plans are real outputs of the deterministic code.') : null,
    h('h2', null, 'How to read a screen'),
    h('p', null, 'The site is laid out like the phone app it demonstrates, and it uses the app’s three signals. A value in the ',
      h('span', { class: 'fig' }, 'figure colour'), ' was computed by Python. A sentence in ',
      h('span', { class: 'serif' }, 'serif'), ' was written by the model. A ',
      h('span', { class: 'muted' }, 'muted'), ' card is a deliberate refusal: the system declining to state something it could not ground, not an error.'),
    h('h2', null, 'The pipeline'),
    pipelineDiagram(),
    h('ol', { class: 'steps' },
      h('li', null, h('strong', null, 'Synthetic vault.'), ' Four invented people, each with about half a year of Apple-Health-style data. No real person’s data appears anywhere on this site.'),
      h('li', null, h('strong', null, 'Deterministic analysis.'), ' Weekly series, trends, plan feasibility and the plan itself are computed by ordinary code.'),
      h('li', null, h('strong', null, 'Fact set.'), ' What the code computed for a question, as labelled values with a plain name for what produced each. This is what the Sources row under an answer reveals.'),
      h('li', null, h('strong', null, 'LLM narration.'), ' The model writes the sentence around those facts.'),
      h('li', null, h('strong', null, 'Verification gate.'), ' Each figure in the sentence is checked against the fact set. If the draft states something unsupported, the answer falls back to a deterministic template and is labelled “Answer withheld”.'),
      h('li', null, h('strong', null, 'Frozen bundle.'), ' Everything was generated offline in advance, checked by script, and frozen into JSON files.'),
      h('li', null, h('strong', null, 'This site.'), ' A small read-only service that serves those files. There is no login, no cookie, no database, and no model call when you use it.')),
    h('h2', null, 'What made this bundle'),
    kv([
      ['Narration model', m.model],
      m.plan_model !== m.model ? ['Plan model', m.plan_model] : null,
      unique.length ? ['Provider', unique.join(', ')] : null,
      m.reasoning ? ['Reasoning setting', m.reasoning] : null,
      ['Generated', fmtTimestamp(manifest.generated_at)],
      ['Data as of', fmtDay(manifest.end_date, true)],
      ['Engine revision', h('code', null, manifest.engine_sha)],
    ]),
    h('h2', null, 'Known limitations'),
    h('ul', null,
      h('li', null, 'Every answer was generated once and frozen. You are reading one run of the model, not a live conversation, so the wording is one draft among many possible ones. You can tap a question but you cannot type one.'),
      h('li', null, 'Only the first week of a plan is written out session by session. Later weeks carry words only (a phase, an intent and a key session), with no training amounts.'),
      h('li', null, 'Nobody is signed in. Choosing a person and a goal only decides which pre-generated screens you see; nothing is stored on the server.'),
      h('li', null, 'Goals beyond running (weight, muscle, sleep, daily movement) were tested and included only where they worked.')),
    h('h2', null, 'The engine'),
    h('p', null, 'The deterministic engine is open source: ',
      h('a', { href: 'https://github.com/rkutyna/fitness-analyst-ai', rel: 'noopener' }, 'github.com/rkutyna/fitness-analyst-ai'),
      '. The source of this site is at ',
      h('a', { href: 'https://github.com/rkutyna/fitness-analyst-demo', rel: 'noopener' }, 'github.com/rkutyna/fitness-analyst-demo'), '.'),
    h('p', null, h('a', { href: '#/' }, 'Back to the people')));
}
