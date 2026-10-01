// First run: the onboarding interview as a plain transcript (each question in
// serif above its answer), the cards Python computed along the way, then the
// first week for review with an Accept button that enters the app. The
// person's answers are scripted; nothing is sent anywhere.
import { h } from './dom.js';
import { card, cardLabel, screenTitle, list, isRecord } from './components.js';
import { miniBars } from './charts.js';
import { longPlanDraft } from './plan.js';
import { humanize } from './format.js';

function row(term, ...detail) {
  return h('div', { class: 'kv-row' }, h('dt', null, term), h('dd', null, ...detail));
}

const fig = (text) => h('span', { class: 'fig' }, text);

// A figure is the string Python wrote in the card's `display` mirror, printed as
// given. Where the mirror has no string for a number, say so; never print the raw.
const shown = (display, ...path) => {
  let at = display;
  for (const key of path) at = isRecord(at) || Array.isArray(at) ? at[key] : undefined;
  return typeof at === 'string' && at ? at : null;
};
const figOr = (text) => (text ? fig(text) : h('span', { class: 'secondary' }, 'not available'));

function historyCard(d, display) {
  const counts = Object.keys(isRecord(d.workout_counts) ? d.workout_counts : {});
  const four = isRecord(d.four_week_jog_minutes) ? d.four_week_jog_minutes : null;
  const weeks = four ? list(four.weeks) : [];
  const weekText = weeks.map((_, i) => shown(display, 'four_week_jog_minutes', 'weeks', i));
  return h('dl', { class: 'kv' },
    row('Recorded history', figOr(shown(display, 'days_of_history')), d.as_of ? ` · through ${d.as_of}` : ''),
    row('Workouts logged', counts.length
      ? counts.map((k, i) => [i ? ' · ' : '', `${humanize(k)} `, figOr(shown(display, 'workout_counts', k))])
      : 'None'),
    four ? row('Jog minutes, last 4 weeks',
      miniBars(weeks, weekText.every(Boolean) ? weekText : null),
      h('span', { class: 'kv-sub' }, figOr(shown(display, 'four_week_jog_minutes', 'mean')), ' a week on average · ',
        figOr(shown(display, 'four_week_jog_minutes', 'last_week')), ' last week')) : null,
    row('Longest continuous block', d.longest_qualified_block_min == null
      ? 'None recorded' : figOr(shown(display, 'longest_qualified_block_min'))),
    d.sleep_midpoint_sd_hours == null ? null
      : row('Sleep timing variability', figOr(shown(display, 'sleep_midpoint_sd_hours'))));
}

function constraintsCard(d) {
  const items = list(d.constraints).filter(isRecord);
  if (!items.length) return h('p', { class: 'row secondary' }, 'Nothing to plan around.');
  return h('ul', { class: 'constraint-list' }, items.map((c) => {
    const where = [c.side, c.site].filter(Boolean).join(' ');
    const tags = [c.kind, c.severity, c.until ? `until ${c.until}` : null].filter(Boolean).join(' · ');
    return h('li', null,
      h('p', { class: 'row' }, humanize(where || c.kind || 'constraint'), tags ? h('span', { class: 'chrome' }, ` · ${tags}`) : null),
      c.text ? h('blockquote', null, c.text) : null);
  }));
}

function structureLines(d, display) {
  const horizon = isRecord(d.plan_horizon) ? d.plan_horizon : null;
  let toward = null;
  if (horizon && horizon.date) toward = [`Horizon: ${humanize(horizon.kind ?? 'date').toLowerCase()} `, fig(horizon.date), '.'];
  else if (horizon && horizon.weeks != null) toward = [`Horizon: ${String(horizon.kind ?? 'rolling')} `, figOr(shown(display, 'plan_horizon', 'weeks')), '.'];
  return [
    d.checkin_weekday ? h('p', { class: 'row secondary' }, `Check-in day: ${d.checkin_weekday}.`) : null,
    d.block_length_weeks != null ? h('p', { class: 'row secondary' }, 'Block length: ', figOr(shown(display, 'block_length_weeks')), '.') : null,
    toward ? h('p', { class: 'row secondary' }, toward) : null,
  ];
}

function genericValue(value, display) {
  if (value == null) return '—';
  if (Array.isArray(value)) return value.map((v, i) => genericValue(v, Array.isArray(display) ? display[i] : null)).join(', ');
  if (typeof value === 'object') {
    return Object.entries(value).map(([k, v]) => `${humanize(k)}: ${genericValue(v, isRecord(display) ? display[k] : null)}`).join('; ');
  }
  if (typeof value === 'number') return typeof display === 'string' && display ? display : 'not available';
  return String(value);
}

const TITLES = {
  history: 'Your recorded history',
  availability: 'Availability',
  constraints: 'Things to plan around',
  structure: 'Your plan structure',
};

function computedCard(c) {
  const data = isRecord(c.data) ? c.data : {};
  const display = isRecord(c.display) ? c.display : null;
  const body = c.kind === 'history' ? historyCard(data, display)
    : c.kind === 'constraints' ? constraintsCard(data)
    : c.kind === 'structure' ? structureLines(data, display)
    : h('dl', { class: 'kv' }, Object.entries(data).map(([k, v]) => row(humanize(k), genericValue(v, display ? display[k] : null))));
  return card('computed', cardLabel(TITLES[c.kind] ?? humanize(c.kind), 'is-accent'), body);
}

function transcript(interview) {
  return h('ol', { class: 'intake', 'aria-label': 'Onboarding interview' }, interview.transcript.map((turn) => (turn.role === 'coach'
    ? h('li', { class: 'intake-q' },
      h('p', { class: 'intake-question' }, h('span', { class: 'sr-only' }, 'Question: '), turn.text),
      turn.card ? computedCard(turn.card) : null)
    : h('li', { class: 'intake-a' }, h('p', { class: 'intake-answer' }, h('span', { class: 'sr-only' }, 'Answer: '), turn.text)))));
}

/** The "Week 1" review card: the week's intent, each day, anything refused,
 *  what is worth knowing, and the drafted long plan. */
function reviewCard(plan) {
  const week = plan.week;
  const first = list(plan.outline).find((w) => w.week === 1);
  const rejected = list(plan.rejected);
  const warnings = list(plan.warnings);
  return card('review',
    cardLabel('Week 1', 'is-accent'),
    first && first.intent ? h('p', { class: 'narration secondary' }, first.intent) : null,
    week ? h('dl', { class: 'review-days' }, week.days.map((day) => h('div', null,
      h('dt', null, day.weekday), h('dd', null, day.title))))
      : h('p', { class: 'narration secondary' }, 'The week preview is not available right now.'),
    rejected.length ? [h('p', { class: 'review-sub is-fault' }, `${rejected.length} ${rejected.length === 1 ? 'item' : 'items'} could not be written:`),
      rejected.map((t) => h('p', { class: 'chrome is-fault' }, t))] : null,
    warnings.length ? [h('p', { class: 'review-sub is-attention' }, 'Worth knowing'),
      warnings.map((t) => h('p', { class: 'chrome secondary' }, t))] : null,
    plan.long_plan ? longPlanDraft(plan.long_plan) : null);
}

export function firstRunView(interview, plan, { base, onEnter }) {
  const enter = (attrs, text) => h('a', { ...attrs, href: `${base}/today`, onclick: onEnter }, text);
  return h('div', { class: 'stack firstrun' },
    h('header', { class: 'nav-bar is-split' },
      screenTitle('Welcome', { small: true }),
      enter({ class: 'pill nav-action' }, 'Skip to the app')),
    transcript(interview),
    reviewCard(plan),
    h('p', null, enter({ class: 'btn-primary' }, 'Accept')));
}
