// The app's shared pieces: the card, its small label, the refusal, the entry
// row and the bullet row. Labels keep their real casing in the DOM; the
// uppercase is CSS only, so a screen reader reads words, not letters.
import { h } from './dom.js';
import { icon } from './icons.js';

export function cardLabel(text, tone = '') {
  return h('h2', { class: `card-label ${tone}`.trim() }, text);
}

/** Who is speaking, above a message: "You" on the right, the vault's mark and
 *  "Vault" on the left. The visually hidden "said:" gives a screen reader the
 *  author of each message in reading order. */
export function messageAuthor(side, { hidden = false } = {}) {
  const you = side === 'you';
  return h('p', { class: `author author-${side}`, 'aria-hidden': hidden ? 'true' : null },
    you ? null : h('span', { class: 'author-disc', 'aria-hidden': 'true' }, icon('mark', 'icon author-mark')),
    h('span', null, you ? 'You' : 'Vault'),
    hidden ? null : h('span', { class: 'sr-only' }, ' said:'));
}

/** One message in the thread: its author above, then the bubble. */
export function message(side, bubble, opts = {}) {
  return h('div', { class: `msg msg-${side}${opts.cls ? ` ${opts.cls}` : ''}` }, messageAuthor(side, opts), bubble);
}

export function card(cls, ...kids) {
  return h('section', { class: `card ${cls ?? ''}`.trim() }, kids);
}

/** The large title at the top of a tab, or the small centred one of a pushed
 *  screen. It takes focus after navigation. */
export function screenTitle(text, { small = false } = {}) {
  return h('h1', { class: small ? 'nav-title' : 'large-title', tabindex: '-1', 'data-focus': true }, text);
}

const DEFAULT_DETAIL = 'Not available right now.';

/** The body of a designed refusal: its sentence, and the one actionable part. */
export function refusalBody(refusal) {
  const detail = refusal && typeof refusal.detail === 'string' && refusal.detail ? refusal.detail : DEFAULT_DETAIL;
  const remedy = refusal && typeof refusal.remedy === 'string' ? refusal.remedy : null;
  return [h('p', { class: 'refusal-detail' }, detail), remedy ? h('p', { class: 'remedy' }, remedy) : null];
}

/** A refusal the system issued on purpose: a card like any other, no icon, no
 *  alarm. */
export function refusalCard(label, refusal, tone = '') {
  return card('refusal', cardLabel(label, tone), refusalBody(refusal));
}

/** An actual fault: the screen could not read what it was sent. */
export function faultCard(label, detail) {
  return card('fault', cardLabel(label, 'is-fault'), h('p', { class: 'fault-detail' }, detail));
}

/** A row of plan prose: a plain bullet, or a disclosure when it has a reason. */
export function bulletRow(line) {
  if (line.detail) {
    return h('details', { class: 'bullet' },
      h('summary', null, h('span', { class: 'bullet-text' }, line.text), icon('down', 'icon chev')),
      h('p', { class: 'bullet-detail' }, line.detail));
  }
  return h('p', { class: 'bullet plain' }, h('span', { class: 'dot', 'aria-hidden': 'true' }, '•'), ' ', line.text);
}

/** An "entry" card: a stroked row that goes somewhere. */
export function entryLink(href, iconName, text, attrs = {}) {
  return h('a', { class: 'entry', href, ...attrs },
    icon(iconName, 'icon entry-icon'), h('span', { class: 'entry-text' }, text), icon('chevron', 'icon chev'));
}

export function isRecord(value) {
  return value != null && typeof value === 'object' && !Array.isArray(value);
}

export function list(value) {
  return Array.isArray(value) ? value : [];
}
