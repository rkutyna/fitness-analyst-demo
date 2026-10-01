// Figures inside answer text. An answer's verified figures arrive in the
// bundle as display strings; every EXACT occurrence of one in the narration is
// wrapped in a span that wears the figure colour. Nothing is parsed, rounded
// or matched loosely: a string that is not in the text verbatim is left alone.
// Only a figure-sized string is wrapped: one with at least one digit and at
// most MAX_FIGURE_LENGTH characters. Plan answers list whole Python-composed
// lines and words like "Base" among their figures, and wrapping those would
// colour whole sentences that embed model-written text.
// The output is text nodes and spans only, so bundle text is never markup.
import { h } from './dom.js';

const WORD = /[\p{L}\p{N}]/u;
const DIGIT = /\d/;
export const MAX_FIGURE_LENGTH = 32;

/** Unique display strings that look like a figure (a digit, at most 32
 *  characters), longest first, so "Monday, August 31" wins over a bare "31"
 *  at the same place. */
export function figureStrings(figures) {
  const seen = new Set();
  for (const figure of figures ?? []) {
    const text = figure && typeof figure.display === 'string' ? figure.display : '';
    if (DIGIT.test(text) && [...text].length <= MAX_FIGURE_LENGTH) seen.add(text);
  }
  return [...seen].sort((a, b) => b.length - a.length);
}

// A match must stand alone: "1" does not match inside "31", "12" or "1.5".
function standsAlone(text, start, end) {
  const first = text[start];
  const last = text[end - 1];
  const before = text[start - 1];
  const after = text[end];
  if (before !== undefined && WORD.test(first) && WORD.test(before)) return false;
  if (after !== undefined && WORD.test(last) && WORD.test(after)) return false;
  if (DIGIT.test(first) && (before === '.' || before === ',') && DIGIT.test(text[start - 2] ?? '')) return false;
  if (DIGIT.test(last) && (after === '.' || after === ',') && DIGIT.test(text[end + 1] ?? '')) return false;
  return true;
}

/** `text` cut into `{ text, figure }` pieces, in order; joined they are `text`. */
export function splitFigures(text, figures) {
  const source = String(text);
  const wanted = figureStrings(figures);
  const pieces = [];
  let plain = '';
  let i = 0;
  while (i < source.length) {
    const hit = wanted.find((w) => source.startsWith(w, i) && standsAlone(source, i, i + w.length));
    if (hit) {
      if (plain) pieces.push({ text: plain, figure: false });
      plain = '';
      pieces.push({ text: hit, figure: true });
      i += hit.length;
    } else {
      plain += source[i];
      i += 1;
    }
  }
  if (plain) pieces.push({ text: plain, figure: false });
  return pieces;
}

/** The same text as DOM children: plain strings and `span.fig` elements. */
export function highlightFigures(text, figures) {
  return splitFigures(text, figures).map((piece) => (piece.figure ? h('span', { class: 'fig' }, piece.text) : piece.text));
}
