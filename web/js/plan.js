// The long plan card and the notes that travel with a plan. The position
// label ("Week 1 of 12"), the phase labels and the current/past flags are all
// Python's, read from the bundle; the one sentence of intent per week is the
// plan model's, so it is serif. Weeks after the first carry words only.
import { h, nextId } from './dom.js';
import { card, cardLabel, list } from './components.js';
import { icon } from './icons.js';
import { fmtRange, raw } from './format.js';

export function longPlanRow(week) {
  const cls = ['lp-week', week.is_current ? 'is-current' : '', week.is_past && !week.is_current ? 'is-past' : ''].filter(Boolean).join(' ');
  return h('li', { class: cls, 'aria-current': week.is_current ? 'step' : null },
    h('div', { class: 'lp-top' },
      h('span', { class: 'lp-index' }, `Week ${week.index}`),
      h('span', { class: 'lp-dates' }, fmtRange(week.start, week.end)),
      week.is_current ? h('span', { class: 'lp-now' }, 'This week') : null),
    week.withheld ? h('p', { class: 'lp-withheld' }, 'Not available') : [
      week.phase_label ? h('p', { class: 'lp-phase' }, week.phase_label) : null,
      week.intent ? h('p', { class: 'lp-intent' }, week.intent) : null,
      week.key_session_label ? h('p', { class: 'lp-key' }, 'Key session: ', week.key_session_label) : null,
    ]);
}

function longPlanTitle(plan) {
  const current = plan.weeks.find((w) => w.is_current);
  if (plan.position_label && current) {
    return current.phase_label && !current.withheld ? `${plan.position_label} · ${current.phase_label}` : plan.position_label;
  }
  return `Your plan · ${plan.weeks_total} weeks`;
}

/** The collapsible long-plan card. Collapsed, it shows the current week;
 *  expanded, every week, the current one marked and past ones dimmed. */
export function longPlanCard(plan, { expanded = false } = {}) {
  const hasCurrent = plan.weeks.some((w) => w.is_current);
  const listId = nextId('lp');
  const rows = plan.weeks.map((week) => {
    const row = longPlanRow(week);
    if (!expanded && !week.is_current) row.setAttribute('hidden', '');
    return { week, row };
  });
  const listEl = h('ol', { class: 'long-plan-list', id: listId }, rows.map((r) => r.row));
  if (!expanded && !hasCurrent) listEl.setAttribute('hidden', '');
  const button = h('button', {
    type: 'button', class: 'lp-toggle', 'aria-expanded': String(expanded), 'aria-controls': listId,
    onclick: () => {
      const open = button.getAttribute('aria-expanded') !== 'true';
      button.setAttribute('aria-expanded', String(open));
      rows.forEach(({ week, row }) => { row.hidden = !open && !week.is_current; });
      listEl.hidden = !open && !hasCurrent;
    },
  }, h('span', { class: 'card-title' }, longPlanTitle(plan)), icon('down', 'icon chev'));
  return h('section', { class: 'card entry-card long-plan' }, h('h2', { class: 'lp-heading' }, button), listEl);
}

/** Every week, open: the drafted plan as onboarding shows it. */
export function longPlanDraft(plan) {
  return h('div', { class: 'lp-draft' },
    h('h3', { class: 'card-title' }, `Your ${plan.weeks_total}-week plan`),
    h('ol', { class: 'long-plan-list' }, plan.weeks.map(longPlanRow)));
}

const STATUS_WORDS = { ok: 'Passed the plan checks', rejected: 'Refused by the plan checks', no_sessions: 'No sessions planned' };

function outlineCard(items) {
  return card('outline',
    cardLabel('The weeks ahead'),
    h('p', { class: 'chrome' }, 'A sparse outline drafted with the plan. Only the first week is saved as the plan; these later targets are sanity-checked, not enforced.'),
    h('ol', { class: 'outline-list' }, items.map((w) => h('li', null,
      h('p', { class: 'lp-top' }, h('span', { class: 'lp-index' }, `Week ${w.week}`),
        w.jog_minutes_target != null ? h('span', { class: 'fig' }, `${raw(w.jog_minutes_target)} min jogging`) : null),
      w.intent ? h('p', { class: 'lp-intent' }, w.intent) : null,
      w.key_session ? h('p', { class: 'lp-key' }, 'Key session: ', w.key_session) : null))));
}

/** What the plan carries besides its week: the reason, the things worth
 *  knowing, anything refused, and the old outline when there is no long plan. */
export function planNotes(plan) {
  const warnings = list(plan.warnings);
  const rejected = list(plan.rejected);
  const outline = list(plan.outline);
  return [
    plan.explanation ? card('why', cardLabel('Why this plan'), h('p', { class: 'narration secondary' }, plan.explanation)) : null,
    warnings.length ? card('warnings', cardLabel('Worth knowing', 'is-attention'),
      h('ul', { class: 'note-list' }, warnings.map((t) => h('li', null, t)))) : null,
    rejected.length ? card('rejected fault', cardLabel('Could not be written', 'is-fault'),
      h('ul', { class: 'note-list' }, rejected.map((t) => h('li', null, t)))) : null,
    !plan.long_plan && outline.length ? outlineCard(outline) : null,
    h('p', { class: 'chrome plan-status' }, [
      STATUS_WORDS[plan.status] ?? plan.status,
      plan.accepted ? 'Accepted' : 'Not accepted',
      `${plan.attempts} ${plan.attempts === 1 ? 'attempt' : 'attempts'}`,
    ].join(' · ')),
  ];
}
