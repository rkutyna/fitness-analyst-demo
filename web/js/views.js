// The screens before the app: the landing page with the four people, and a
// person's three goals. Entering a goal opens the app as that person.
import { h } from './dom.js';
import { getJSON } from './api.js';
import { card, cardLabel, refusalCard } from './components.js';
import { icon } from './icons.js';
import { splitLabel } from './format.js';

// The number and unit on each card are the series' `headline`, picked and
// formatted by Python (the last complete week). Nothing is computed here.
const STATS = [
  { metric: 'jog_minutes', label: 'Jogging / wk' },
  { metric: 'resting_heart_rate', label: 'Resting HR' },
  { metric: 'step_count', label: 'Steps / day', showUnit: false },
];

function statItem(overview, spec) {
  const series = overview.series.find((x) => x.metric === spec.metric);
  const headline = series && series.headline;
  const unit = headline && spec.showUnit !== false ? headline.unit : '';
  return h('div', { class: 'metric' },
    h('dt', { class: 'card-label' }, spec.label),
    h('dd', null, h('span', { class: 'fig' }, headline ? headline.display : '—'),
      unit ? h('span', { class: 'stat-unit' }, ` ${unit}`) : null));
}

async function personCard(person) {
  const overview = await getJSON(`/api/people/${person.id}/overview`);
  const { name, role } = splitLabel(person.label);
  return h('li', null, h('a', { class: 'card person-card', href: `#/p/${person.id}` },
    h('span', { class: 'person-head' },
      h('span', { class: 'avatar', 'aria-hidden': 'true' }, name.charAt(0)),
      h('span', null, h('span', { class: 'card-title' }, name), role ? h('span', { class: 'role' }, role) : null),
      icon('chevron', 'icon chev')),
    h('span', { class: 'blurb' }, person.blurb),
    h('dl', { class: 'metrics' }, STATS.map((spec) => statItem(overview, spec)))));
}

export async function landingView(tree) {
  const cards = await Promise.all(tree.people.map(personCard));
  return h('div', { class: 'stack' },
    h('h1', { class: 'large-title', tabindex: '-1', 'data-focus': true }, 'A running coach whose numbers can’t be made up'),
    h('p', { class: 'lead' }, 'Every number in this app is computed by deterministic Python from the user’s health data. The language model only narrates those numbers. Pick a person to open the app as them.'),
    h('section', { class: 'stack', 'aria-labelledby': 'people-h' },
      h('h2', { id: 'people-h', class: 'card-label' }, 'People'),
      h('ul', { class: 'card-list' }, cards),
      h('p', { class: 'chrome' }, 'Figures on the cards are the last full week of each person’s data.')));
}

export function personView(person) {
  const { name, role } = splitLabel(person.label);
  return h('div', { class: 'stack' },
    h('header', { class: 'nav-bar' },
      h('a', { class: 'back', href: '#/' }, icon('back', 'icon'), h('span', { class: 'sr-only' }, 'Back to the people')),
      h('h1', { class: 'nav-title', tabindex: '-1', 'data-focus': true }, name)),
    card('person-intro', role ? cardLabel(role) : null, h('p', { class: 'row' }, person.blurb)),
    h('section', { class: 'stack', 'aria-labelledby': 'goals-h' },
      h('h2', { id: 'goals-h', class: 'card-label' }, 'Choose a goal'),
      h('ul', { class: 'card-list' }, person.goals.map((g) => h('li', null,
        h('a', { class: 'card goal-card', href: `#/p/${person.id}/g/${g.id}` },
          h('span', { class: 'person-head' }, h('span', { class: 'card-title' }, g.label), icon('chevron', 'icon chev')),
          h('span', { class: 'blurb' }, g.blurb))))),
      h('p', { class: 'chrome' }, `Opens the app as ${name} with that goal, starting with onboarding.`)));
}

export function notFoundView() {
  return h('div', { class: 'stack' },
    h('h1', { class: 'large-title', tabindex: '-1', 'data-focus': true }, 'Not found'),
    refusalCard('Nothing here', { detail: 'There is nothing at this address.' }, 'is-refuse'),
    h('p', null, h('a', { href: '#/' }, 'Back to the people')));
}
