// The coach's daily briefs, as the app shows them: the closing narration under
// the day on Today, and the whole brief (Python's facts block, then the
// narration) in a day view opened from Reports. Nothing here is derived. The
// text is printed as it was written, one line at a time, in text nodes only;
// figures are marked only where a fact's value appears in the narration
// verbatim; and "Written ..." is the stored timestamp rearranged as text, with
// no clock arithmetic and no timezone conversion.
import { h } from './dom.js';
import { card, cardLabel, entryLink, isRecord, list, refusalCard, screenTitle } from './components.js';
import { answerText, FALLBACK_NOTE, sourcesView, tracedLine } from './answer.js';
import { icon } from './icons.js';

const MONTHS = {
  '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun',
  '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec',
};
const INSTANT = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$/;
const UTC_OFFSETS = ['Z', '+00:00', '+0000', '-00:00', '-0000'];
const NOT_SAID = 'The vault did not say when this was written.';

/** "Written 31 Aug 2026 at 05:00 UTC" from "2026-08-31T05:00:00+00:00". The
 *  date and time are the stored ones, cut apart and put back in the app's
 *  order; the stored offset is named and never applied, so the time is the one
 *  that was written, not one converted into the reader's zone. A value that is
 *  not an instant is shown as it arrived. */
export function writtenLine(raw) {
  if (typeof raw !== 'string' || !raw.trim()) return NOT_SAID;
  const text = raw.trim();
  const m = INSTANT.exec(text);
  if (!m || !MONTHS[m[2]]) return `Written ${text}`;
  const [, year, month, day, hour, minute, offset] = m;
  const zone = offset ? ` ${UTC_OFFSETS.includes(offset) ? 'UTC' : offset}` : '';
  return `Written ${day.replace(/^0/, '')} ${MONTHS[month]} ${year} at ${hour}:${minute}${zone}`;
}

/** The facts as figures for the highlighter: their values, as published. */
function factFigures(entry) {
  return list(entry.facts).filter(isRecord).map((fact) => ({ display: fact.value }));
}

const hasText = (value) => typeof value === 'string' && value.trim() !== '';

// ---- the narration, on Today ------------------------------------------------------------
/** The entry whose narration Today shows for `date`: the evening one when it
 *  has a narration, else the morning one. Null when the day has none. */
export function pickBrief(briefs, date) {
  const entries = list(briefs && briefs.entries).filter(isRecord).filter((e) => e.date === date && hasText(e.narration));
  return entries.find((e) => e.kind === 'evening') ?? entries.find((e) => e.kind === 'morning') ?? entries[0] ?? null;
}

function fallbackNote(entry) {
  const reason = isRecord(entry.verification) && entry.verification.reason;
  return h('p', { class: 'note' }, FALLBACK_NOTE, reason ? ` The verifier said: ${reason}.` : '');
}

/** The brief's closing paragraph under the day. A narration is the model's
 *  sentence, so it is serif and carries "The coach's own words". A fallback is
 *  Python's own fixed sentence: sans, no claim about the coach, and the same
 *  honest note a fallback answer carries in Chat. */
export function todayBriefCard(entry) {
  const fallback = entry.mode === 'fallback';
  return card(`brief${fallback ? ' is-fallback' : ''}`,
    cardLabel(entry.label, fallback ? 'is-refuse' : ''),
    h('p', { class: 'chrome brief-provenance' },
      `${fallback ? 'Python’s own text' : 'The coach\'s own words'} · ${writtenLine(entry.written_at)}`),
    answerText(entry.narration, fallback ? [] : factFigures(entry), fallback ? 'template' : 'narration'),
    fallback ? fallbackNote(entry) : null);
}

// ---- the whole brief, in the day view -----------------------------------------------------
const MARKERS = {
  '•': ['dot', ''],
  '✓': ['done', 'Done. '],
  '✗': ['missed', 'Not done. '],
};

/** One line of Python's facts block: a marked line keeps its glyph in a column
 *  of its own so a wrapped sentence hangs beside it; anything else is a
 *  paragraph. Only the glyph and the one space after it are lifted out. */
function briefLine(line) {
  const head = line.replace(/^[ \t]+/, '');
  const glyph = Object.keys(MARKERS).find((g) => head.startsWith(g));
  if (!glyph) return h('p', { class: 'brief-line' }, line);
  const [tone, spoken] = MARKERS[glyph];
  const rest = head.slice(glyph.length);
  return h('p', { class: 'brief-line brief-bullet' },
    h('span', { class: `brief-marker marker-${tone}`, 'aria-hidden': 'true' }, glyph),
    spoken ? h('span', { class: 'sr-only' }, spoken) : null,
    h('span', { class: 'brief-text' }, rest.startsWith(' ') ? rest.slice(1) : rest));
}

/** Blocks of lines, a blank line ending a block. */
function lineBlocks(text, cls) {
  const box = h('div', { class: cls });
  let lines = [];
  const flush = () => { if (lines.length) box.append(h('div', { class: 'brief-block' }, lines.map(briefLine))); lines = []; };
  for (const line of String(text).split('\n')) {
    if (line.trim() === '') flush(); else lines.push(line);
  }
  flush();
  return box;
}

/** The brief's full text: Python's facts block in sans, then the narration.
 *  The narration is the tail of `text`, so the head is the facts block. A
 *  fallback is all Python's, so it is all sans and nothing in it is marked. */
export function briefProse(entry) {
  const fallback = entry.mode === 'fallback';
  const text = String(entry.text);
  const tail = hasText(entry.narration) && text.endsWith(entry.narration) ? entry.narration : null;
  const head = tail ? text.slice(0, text.length - tail.length) : text;
  return h('div', { class: 'brief-prose' },
    head.trim() !== '' ? lineBlocks(head, 'brief-facts') : null,
    tail ? answerText(tail, fallback ? [] : factFigures(entry), fallback ? 'template' : 'narration') : null);
}

/** One brief as an entry card: its label, when it was written, the text, and
 *  under a hairline what the Chat answer's footer carries: how many figures
 *  were traced, and the collapsed Sources row with the facts table. */
export function briefEntryCard(entry) {
  const fallback = entry.mode === 'fallback';
  const facts = list(entry.facts).filter(isRecord);
  return card(`brief${fallback ? ' is-fallback' : ''}`,
    cardLabel(entry.label, fallback ? 'is-refuse' : ''),
    h('p', { class: 'chrome brief-provenance' }, writtenLine(entry.written_at)),
    briefProse(entry),
    fallback ? fallbackNote(entry) : null,
    h('div', { class: 'answer-foot' },
      tracedLine(entry, !fallback),
      sourcesView({ sources: [], facts }, facts.length)));
}

/** The dates the file has briefs for, in the order it lists them. */
export function briefDates(briefs) {
  const seen = [];
  for (const entry of list(briefs && briefs.entries).filter(isRecord)) {
    if (typeof entry.date === 'string' && !seen.includes(entry.date)) seen.push(entry.date);
  }
  return seen;
}

/** The Reports tab's entry into the briefs: one card, or one per day when the
 *  file covers several. Null when the goal has no briefs at all. */
export function briefsEntry(briefs, base) {
  const dates = briefDates(briefs);
  if (!dates.length) return null;
  return h('section', { class: 'stack briefs', 'aria-label': 'Daily briefs', 'data-slot': 'briefs' },
    dates.map((date) => entryLink(`${base}/reports/briefs/${encodeURIComponent(date)}`, 'today',
      h('span', { class: 'entry-stack' },
        h('span', null, dates.length > 1 ? `Daily briefs · ${date}` : 'Daily briefs'),
        h('span', { class: 'chrome entry-sub' }, 'The morning and evening briefs, day by day.')))));
}

/** One day's briefs, opened from Reports; back returns to Reports. */
export function briefsDayView(briefs, date, base) {
  const entries = list(briefs && briefs.entries).filter(isRecord).filter((e) => e.date === date);
  const back = h('a', { class: 'back', href: `${base}/reports` }, icon('back', 'icon'), h('span', { class: 'sr-only' }, 'Back to Reports'));
  return h('div', { class: 'stack' },
    h('header', { class: 'nav-bar' }, back, screenTitle(date, { small: true })),
    entries.length ? entries.map(briefEntryCard)
      : refusalCard('Daily briefs', { detail: `There are no briefs for ${date}.` }, 'is-refuse'));
}
