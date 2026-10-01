// One day, as the app's Today screen shows it: the planned session cards, the
// readiness card and the look back at the day before. Each section is either
// a payload or a designed refusal, and any of them may refuse. Every figure is
// printed from its `display` string; nothing is recomputed, and unknown keys
// are ignored.
import { h } from './dom.js';
import { card, cardLabel, refusalBody, refusalCard, faultCard, bulletRow, isRecord, list } from './components.js';
import { icon } from './icons.js';
import { humanize } from './format.js';

export const TITLES = {
  today: { plan: 'Today’s session', yesterday: 'Yesterday' },
  day: { plan: 'Session', yesterday: 'The day before' },
};
const UNREADABLE = 'This screen could not read the section it was sent. The data is fine.';

/** 'payload' | 'refusal' | 'unreadable'. `status` is an open set: "empty" and
 *  "unavailable" refuse, anything else is a payload if it reads as one. */
function kindOf(section, readable) {
  if (!isRecord(section)) return 'unreadable';
  if (section.status === 'empty' || section.status === 'unavailable') return 'refusal';
  if (readable(section)) return 'payload';
  return section.reason || section.detail ? 'refusal' : 'unreadable';
}

function section(label, value, readable, render) {
  const kind = kindOf(value, readable);
  if (kind === 'payload') return render(value);
  if (kind === 'refusal') return refusalCard(label, value);
  return faultCard(label, UNREADABLE);
}

const display = (figure) => (isRecord(figure) && typeof figure.display === 'string' ? figure.display : null);

// ---- the plan -----------------------------------------------------------------
export function saysOnlyRest(title) {
  const text = String(title ?? '').trim().toLowerCase().replace(/[.!]+$/, '').trim();
  return ['', 'rest', 'rest day'].includes(text);
}

export function restMarker(heading = false) {
  return h('p', { class: heading ? 'rest-marker is-heading' : 'rest-marker' }, icon('rest', 'icon inline'), 'Rest day');
}

function sessionLine(line) {
  if (!isRecord(line) || typeof line.text !== 'string') return null;
  if (line.kind === 'dose') return h('p', { class: 'line-dose' }, line.text);
  if (line.kind === 'heading') return h('p', { class: 'line-heading' }, line.text);
  return bulletRow(line);
}

/** One typed session: its label titles the card, its title is the headline. */
export function sessionCard(session) {
  const label = session.label || (session.modality ? humanize(session.modality) : 'Session');
  const headline = session.title && session.title !== label ? session.title : null;
  return card('session',
    cardLabel(label),
    session.status ? h('p', { class: 'session-status' }, session.status) : null,
    headline ? h('p', { class: 'card-title' }, headline) : null,
    list(session.lines).map(sessionLine));
}

function planCards(plan, title) {
  const sessions = list(plan.sessions).filter(isRecord);
  const anchors = list(plan.anchors).filter(isRecord);
  const cards = sessions.map(sessionCard);
  if (!sessions.length) {
    const rest = plan.is_rest_day === true;
    const headline = rest && saysOnlyRest(plan.session_title) ? null : plan.session_title;
    cards.push(card('session',
      cardLabel(title),
      headline ? h('p', { class: 'card-title' }, headline) : null,
      rest ? restMarker(!headline) : null,
      list(plan.session_lines).filter(isRecord).map(bulletRow)));
  }
  if (anchors.length) cards.push(card('session', cardLabel('Anchors'), anchors.map(bulletRow)));
  return cards;
}

// ---- readiness ------------------------------------------------------------------
const BANDS = {
  red: ['recover', 'Recover'], recover: ['recover', 'Recover'],
  amber: ['steady', 'Steady'], steady: ['steady', 'Steady'],
  green: ['strong', 'Strong'], strong: ['strong', 'Strong'],
};

/** The band chip: a three-bar gauge and the band's name. An unknown band is
 *  shown as received, neutral and without a gauge. */
export function bandChip(rawBand) {
  const text = String(rawBand ?? '');
  const known = BANDS[text.toLowerCase()];
  return h('span', { class: `band-chip ${known ? `band-${known[0]}` : 'band-unknown'}` },
    known ? h('span', { class: 'gauge', 'aria-hidden': 'true' }, h('i', null), h('i', null), h('i', null)) : null,
    h('span', { class: 'band-name' }, known ? known[1] : humanize(text)));
}

function metricCell(key, value) {
  return h('div', { class: 'metric' }, h('dt', { class: 'card-label' }, key), h('dd', { class: 'metric-value fig' }, value ?? '—'));
}

function readinessCard(readiness) {
  const parts = isRecord(readiness.components) ? readiness.components : {};
  return card('readiness',
    cardLabel('Readiness'),
    h('p', { class: 'readiness-row' },
      h('span', { class: 'big-figure fig' }, display(readiness.score)),
      readiness.band ? bandChip(readiness.band) : null),
    h('dl', { class: 'metrics' }, metricCell('HRV', display(parts.hrv)), metricCell('Resting HR', display(parts.rhr))),
    readiness.note ? h('p', { class: 'card-note' }, readiness.note) : null);
}

// ---- the day before ---------------------------------------------------------------
const OUTCOMES = { done: 'Done', partial: 'Partially done', swapped: 'Swapped', missed: 'Missed', rest_day: 'Rest day' };
const WORKOUT_FIGURES = [['Duration', 'duration_min'], ['Distance', 'distance_mi'], ['Pace', 'pace_min_per_mi'], ['Avg HR', 'avg_heart_rate']];

function workoutRow(workout) {
  const figures = WORKOUT_FIGURES.map(([label, key]) => [label, display(workout[key])]).filter(([, text]) => text);
  return h('div', { class: 'workout' },
    h('p', { class: 'card-title' }, humanize(workout.type ?? 'workout')),
    figures.length ? h('dl', { class: 'workout-figures' }, figures.map(([label, text]) => h('div', null,
      h('dt', { class: 'card-label' }, label), h('dd', { class: 'fig' }, text)))) : null);
}

function yesterdayCard(yesterday, title) {
  const names = (keys) => list(keys).map(humanize).join(', ');
  return card('yesterday',
    cardLabel(title),
    h('p', { class: 'card-title' }, OUTCOMES[yesterday.outcome] ?? humanize(yesterday.outcome)),
    list(yesterday.credited).length ? h('p', { class: 'row' }, `Credited: ${names(yesterday.credited)}`) : null,
    list(yesterday.substituted).length ? h('p', { class: 'row secondary' }, `Substituted: ${names(yesterday.substituted)}`) : null,
    list(yesterday.workouts).filter(isRecord).map(workoutRow));
}

// ---- the day ----------------------------------------------------------------------
/** "<date> · data through <day>", both printed exactly as they were sent. */
export function freshnessLine(day) {
  const fresh = isRecord(day.freshness) ? day.freshness : {};
  let tail = '';
  if (typeof fresh.data_through === 'string') tail = `data through ${fresh.data_through}`;
  else if ('data_through' in fresh) tail = 'no data yet';
  else if (typeof fresh.as_of === 'string') tail = `as of ${fresh.as_of}`;
  return h('p', { class: 'freshness' }, [day.date, tail].filter(Boolean).join(' · '));
}

/** The cards for one day. `planOnly` is a day that has not happened yet:
 *  only what is planned is shown, not readiness or the look back. */
export function dayCards(day, { titles = TITLES.today, planOnly = false } = {}) {
  const cards = [section(titles.plan, day.plan,
    (p) => typeof p.session_title === 'string' || Array.isArray(p.sessions), (p) => planCards(p, titles.plan))];
  if (!planOnly) {
    cards.push(section('Readiness', day.readiness, (r) => display(r.score) != null, readinessCard));
    cards.push(section(titles.yesterday, day.yesterday, (y) => typeof y.outcome === 'string', (y) => yesterdayCard(y, titles.yesterday)));
  }
  return cards.flat();
}

/** The day the Today tab shows: the one flagged `is_today`, else the one
 *  dated `as_of`. Null when the file has neither. */
export function pickToday(today) {
  const days = list(today && today.days).filter(isRecord);
  return days.find((d) => d.is_today === true) ?? days.find((d) => d.date === today.as_of) ?? null;
}

export function findDay(today, date) {
  return list(today && today.days).filter(isRecord).find((d) => d.date === date) ?? null;
}

/** True for a day after the data ends: the bundle's flag, else the dates as
 *  text (ISO days order as strings). */
export function isFuture(day, today) {
  if (typeof day.is_future === 'boolean') return day.is_future;
  return typeof today.as_of === 'string' && typeof day.date === 'string' && day.date > today.as_of;
}

/** A week day from the plan, shaped like a Today plan section, for a day the
 *  Today file does not cover. */
export function planFromWeekDay(weekDay) {
  return { status: 'ok', session_title: weekDay.title, is_rest_day: weekDay.is_rest_day, sessions: weekDay.sessions, session_lines: [], anchors: [] };
}
