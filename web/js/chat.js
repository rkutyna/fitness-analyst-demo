// The Chat tab. There is no model behind it: each suggestion is a question
// that was asked, answered and verified in advance, and tapping one adds that
// turn to the transcript. The transcript is kept per goal for the life of the
// page, and `?q=<index>` opens with that question already asked.
import { h } from './dom.js';
import { cardLabel, message, screenTitle } from './components.js';
import { vaultMessage } from './answer.js';

const WAIT_MS = 600;
const transcripts = new Map();

function reducedMotion() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Goal questions first, then the person's data questions; a question's
 *  position in this list is its index in the URL. */
export function questionList(goalQa, personQa) {
  return [
    ...goalQa.answers.map((answer) => ({ answer, group: 'plan' })),
    ...personQa.answers.map((answer) => ({ answer, group: 'data' })),
  ];
}

const GROUPS = [['plan', 'About this plan'], ['data', 'About the data']];

export function chatView(goalQa, personQa, { gid, base, initial = null }) {
  const questions = questionList(goalQa, personQa);
  if (!transcripts.has(gid)) transcripts.set(gid, []);
  const asked = transcripts.get(gid);

  // The vault's first message in the thread; it stays above the questions.
  const intro = h('li', { class: 'turn intro' }, message('vault', h('div', { class: 'bubble bubble-vault empty-state' },
    cardLabel('Ask the vault'),
    h('p', { class: 'narration secondary' }, 'Questions are answered from your own data. Every figure is computed, never guessed — and when a number cannot be grounded, the answer is withheld rather than estimated.'))));
  const log = h('ol', { class: 'transcript', role: 'log', 'aria-live': 'polite', 'aria-label': 'Conversation' }, intro);
  const buttons = new Map();
  const groups = GROUPS.map(([key, label]) => {
    const items = questions.map((q, i) => [q, i]).filter(([q]) => q.group === key).map(([q, i]) => {
      const button = h('button', { type: 'button', class: 'suggestion', onclick: () => ask(i) },
        h('span', null, q.answer.question));
      const item = h('li', null, button);
      buttons.set(i, item);
      return item;
    });
    return h('section', { class: 'suggestion-group' }, h('h2', { class: 'card-label' }, label), h('ul', { class: 'suggestion-list' }, items));
  });
  const suggestions = h('div', { class: 'suggestions' }, groups);

  function tidy() {
    groups.forEach((group) => { group.hidden = !group.querySelector('li:not([hidden])'); });
    suggestions.hidden = asked.length >= questions.length;
  }

  function turn(index, instant) {
    const { answer } = questions[index];
    const question = h('p', { class: 'question', tabindex: '-1' }, answer.question);
    // Three pulsing dots; the words are for a screen reader.
    const waiting = message('vault', h('div', { class: 'bubble bubble-vault bubble-waiting' },
      h('span', { class: 'beat', 'aria-hidden': 'true' }, h('i'), h('i'), h('i')),
      h('span', { class: 'sr-only' }, 'Waiting for the vault…')), { hidden: true, cls: 'waiting' });
    const item = h('li', { class: 'turn', id: `turn-${index}` },
      message('you', h('div', { class: 'bubble bubble-you' }, question)));
    const reveal = () => { waiting.remove(); item.append(vaultMessage(answer)); };
    if (instant || reducedMotion()) reveal();
    else { item.append(waiting); setTimeout(reveal, WAIT_MS); }
    buttons.get(index).hidden = true;
    log.append(item);
    return { item, question };
  }

  /** Ask question `index`. Already asked: scroll back to it. */
  function ask(index, { instant = false, quiet = false } = {}) {
    if (!Number.isInteger(index) || index < 0 || index >= questions.length) return;
    const existing = log.querySelector(`#turn-${index}`);
    if (existing) {
      if (!quiet) existing.scrollIntoView({ block: 'start' });
      return;
    }
    if (!asked.includes(index)) asked.push(index);
    const { item, question } = turn(index, instant);
    tidy();
    if (quiet) return;
    history.replaceState(null, '', `${base}/chat?q=${index}`);
    item.scrollIntoView({ block: 'start', behavior: reducedMotion() ? 'auto' : 'smooth' });
    question.focus({ preventScroll: true });
  }

  [...asked].forEach((index) => ask(index, { instant: true, quiet: true }));
  if (initial != null) ask(initial, { instant: true, quiet: true });
  tidy();

  const el = h('div', { class: 'stack chat' },
    h('header', { class: 'nav-bar' }, screenTitle('Chat', { small: true })),
    log, suggestions);
  return { el, ask, focusTurn: initial };
}
