// The Week tab: one card per day of the plan's first week, the notes the plan
// carries, and the long plan. Tapping a day opens it with the same renderer
// the Today tab uses.
import { h } from './dom.js';
import { card, cardLabel, screenTitle, refusalCard, bulletRow, list, isRecord } from './components.js';
import { icon } from './icons.js';
import { longPlanCard, planNotes } from './plan.js';
import { dayCards, freshnessLine, findDay, isFuture, planFromWeekDay, restMarker, saysOnlyRest, TITLES } from './today.js';

function dayCard(day, base) {
  const sessions = list(day.sessions).filter(isRecord);
  return h('article', { class: `card day ${day.is_rest_day ? 'is-rest' : ''}`.trim() },
    h('h3', { class: 'day-head' }, h('a', { class: 'day-link', href: `${base}/week/${day.date}` },
      h('span', { class: 'weekday' }, day.weekday), ' ', h('span', { class: 'day-date' }, day.date),
      icon('chevron', 'icon chev'))),
    sessions.length ? sessions.map((session) => h('div', { class: 'day-session' },
      h('p', { class: 'row secondary' },
        session.label ? h('span', { class: 'session-label' }, session.label) : null,
        session.label && (session.title ?? day.title) ? ' · ' : null,
        session.title ?? day.title),
      list(session.lines).filter(isRecord).map(bulletRow)))
      : (saysOnlyRest(day.title) ? null : h('p', { class: 'row secondary' }, day.title)),
    day.is_rest_day ? restMarker() : null);
}

export function weekView(plan, base) {
  const week = plan.week;
  if (!week) {
    return h('div', { class: 'stack' }, screenTitle('Week'),
      refusalCard('Week', { detail: 'No detailed week is available for this plan.' }, 'is-refuse'),
      planNotes(plan), plan.long_plan ? longPlanCard(plan.long_plan) : null);
  }
  const from = week.window_start ?? week.week_start;
  const to = week.window_end;
  return h('div', { class: 'stack' },
    screenTitle('Week'),
    h('p', { class: 'week-range' }, to ? `${from} – ${to}` : from),
    h('dl', { class: 'totals' }, h('div', null,
      h('dt', { class: 'card-label' }, 'Planned'),
      h('dd', { class: 'metric-value fig' }, `${week.planned_sessions} ${week.planned_sessions === 1 ? 'session' : 'sessions'}`))),
    week.title ? h('h2', { class: 'section-title' }, week.title) : null,
    week.days.map((day) => dayCard(day, base)),
    planNotes(plan),
    plan.long_plan ? longPlanCard(plan.long_plan) : null);
}

/** One day, opened from the week. `today` is the optional Today file (null
 *  when the bundle has none); a day it does not cover, or one that has not
 *  happened yet, shows only what is planned. */
export function dayDetailView(plan, today, date, base) {
  const weekDay = list(plan.week && plan.week.days).find((d) => d.date === date) ?? null;
  const day = today ? findDay(today, date) : null;
  const back = h('a', { class: 'back', href: `${base}/week` }, icon('back', 'icon'), h('span', { class: 'sr-only' }, 'Back to the week'));
  const head = h('header', { class: 'nav-bar' }, back, screenTitle(weekDay ? weekDay.weekday : date, { small: true }));
  if (!weekDay && !day) {
    return h('div', { class: 'stack' }, head, refusalCard('Session', { detail: `The plan does not cover ${date}.` }, 'is-refuse'));
  }
  if (day) {
    return h('div', { class: 'stack' }, head, freshnessLine(day),
      dayCards(day, { titles: TITLES.day, planOnly: isFuture(day, today) }));
  }
  return h('div', { class: 'stack' }, head, h('p', { class: 'freshness' }, date),
    dayCards({ plan: planFromWeekDay(weekDay) }, { titles: TITLES.day, planOnly: true }));
}
