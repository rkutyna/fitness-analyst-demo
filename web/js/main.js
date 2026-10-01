import { getJSON, getOptional } from './api.js';
import { h } from './dom.js';
import { card, cardLabel, screenTitle, refusalCard, entryLink } from './components.js';
import { landingView, personView, notFoundView } from './views.js';
import { aboutView } from './about.js';
import { firstRunView } from './firstrun.js';
import { dayCards, freshnessLine, pickToday } from './today.js';
import { weekView, dayDetailView } from './week.js';
import { chatView } from './chat.js';
import { reportsView } from './reports.js';
import { briefsDayView, pickBrief, todayBriefCard } from './briefs.js';
import { setNotice, setShell, initExplain } from './shell.js';
import { splitLabel } from './format.js';

const main = document.getElementById('main');
let ctx = null;
let token = 0;
let first = true;

// "Seen onboarding for this goal" is a convenience kept for the browser tab
// only. Storage can be unavailable; the app works the same without it.
const seen = {
  has(gid) { try { return sessionStorage.getItem(`seen:${gid}`) === '1'; } catch { return false; } },
  add(gid) { try { sessionStorage.setItem(`seen:${gid}`, '1'); } catch { /* not remembered */ } },
};

// Addresses from the site's earlier layout still land somewhere sensible.
const LEGACY = { interview: 'welcome', plan: 'week', qa: 'chat' };
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function parse() {
  const [path, query = ''] = location.hash.replace(/^#\/?/, '').split('?');
  const parts = path.split('/').filter(Boolean).map(decodeURIComponent);
  if (!parts.length) return { name: 'home' };
  if (parts[0] === 'about' && parts.length === 1) return { name: 'about' };
  if (parts[0] !== 'p' || !parts[1]) return { name: '404' };
  if (parts.length === 2) return { name: 'person', pid: parts[1] };
  if (parts[2] !== 'g' || !parts[3]) return { name: '404' };
  const goal = { pid: parts[1], gid: parts[3] };
  const tab = LEGACY[parts[4]] ?? parts[4];
  if (parts.length === 4) return { name: 'enter', ...goal };
  if (parts.length === 5 && ['welcome', 'today', 'week', 'reports'].includes(tab)) return { name: tab, ...goal };
  if (parts.length === 5 && tab === 'chat') {
    const q = new URLSearchParams(query).get('q');
    return { name: 'chat', ...goal, q: q != null && /^\d+$/.test(q) ? Number(q) : null };
  }
  if (parts.length === 6 && tab === 'week' && ISO_DAY.test(parts[5])) return { name: 'day', ...goal, date: parts[5] };
  if (parts.length === 7 && tab === 'reports' && parts[5] === 'briefs' && ISO_DAY.test(parts[6])) return { name: 'briefs', ...goal, date: parts[6] };
  return { name: '404' };
}

/** The brief shows on the pinned day only, under the cards, and only when the
 *  goal has one for that day. */
function briefCard(briefs, day) {
  const entry = briefs && day ? pickBrief(briefs, day.date) : null;
  return entry ? todayBriefCard(entry) : null;
}

function todayView(today, briefs, base) {
  const day = today ? pickToday(today) : null;
  return h('div', { class: 'stack' },
    screenTitle('Today'),
    day ? [freshnessLine(day), dayCards(day), briefCard(briefs, day)]
      : refusalCard('Today', { detail: 'There is no Today view for this goal yet. The Week tab has the plan.' }, 'is-refuse'),
    entryLink(`${base}/welcome`, 'replay', 'Replay onboarding'),
    entryLink('#/about', 'info', 'About this demo'));
}

async function goalScreen(route, person, goal) {
  const base = `#/p/${person.id}/g/${goal.id}`;
  const api = `/api/goals/${goal.id}`;
  const shell = { person, goal };
  switch (route.name) {
    case 'welcome': {
      const [interview, plan] = await Promise.all([getJSON(`${api}/interview`), getJSON(`${api}/plan`)]);
      return { title: 'Welcome', el: firstRunView(interview, plan, { base, onEnter: () => seen.add(goal.id) }), shell: { ...shell, screen: 'welcome' } };
    }
    case 'today': {
      const [today, briefs] = await Promise.all([getOptional(`${api}/today`), getOptional(`${api}/briefs`)]);
      return { title: 'Today', el: todayView(today, briefs, base), shell: { ...shell, tab: 'today', screen: 'today' } };
    }
    case 'week':
      return { title: 'Week', el: weekView(await getJSON(`${api}/plan`), base), shell: { ...shell, tab: 'week', screen: 'week' } };
    case 'day': {
      const [plan, today] = await Promise.all([getJSON(`${api}/plan`), getOptional(`${api}/today`)]);
      return { title: route.date, el: dayDetailView(plan, today, route.date, base), shell: { ...shell, tab: 'week', screen: 'day' } };
    }
    case 'chat': {
      const [goalQa, personQa] = await Promise.all([getJSON(`${api}/qa`), getJSON(`/api/people/${person.id}/qa`)]);
      const view = chatView(goalQa, personQa, { gid: goal.id, base, initial: route.q });
      return { title: 'Chat', el: view.el, focus: route.q != null ? `#turn-${route.q} .question` : null, shell: { ...shell, tab: 'chat', screen: 'chat' } };
    }
    case 'briefs':
      return { title: `Daily briefs ${route.date}`, el: briefsDayView(await getOptional(`${api}/briefs`), route.date, base), shell: { ...shell, tab: 'reports', screen: 'briefs' } };
    default: {
      const [overview, briefs] = await Promise.all([getJSON(`/api/people/${person.id}/overview`), getOptional(`${api}/briefs`)]);
      return { title: 'Reports', el: reportsView(overview, briefs, base), shell: { ...shell, tab: 'reports', screen: 'reports' } };
    }
  }
}

async function build(route) {
  const { tree, manifest } = ctx;
  const missing = { title: 'Not found', el: notFoundView(), shell: { screen: 'missing' } };
  if (route.name === 'home') return { title: 'People', el: await landingView(tree), shell: { screen: 'home' } };
  if (route.name === 'about') return { title: 'About', el: aboutView(manifest), shell: { screen: 'about' } };
  if (route.name === '404') return missing;
  const person = tree.people.find((p) => p.id === route.pid);
  if (!person) return missing;
  if (route.name === 'person') return { title: splitLabel(person.label).name, el: personView(person), shell: { screen: 'person' } };
  const goal = person.goals.find((g) => g.id === route.gid);
  if (!goal) return missing;
  if (route.name === 'enter') {
    // Entering a goal starts with onboarding, unless it was already seen.
    location.replace(`#/p/${person.id}/g/${goal.id}/${seen.has(goal.id) ? 'today' : 'welcome'}`);
    return null;
  }
  const screen = await goalScreen(route, person, goal);
  return { ...screen, title: `${screen.title} · ${goal.label}` };
}

function failure() {
  return h('div', { class: 'stack' },
    h('h1', { class: 'large-title', tabindex: '-1', 'data-focus': true }, 'Something went wrong'),
    card('fault', cardLabel('Not loaded', 'is-fault'), h('p', { class: 'fault-detail' }, 'The demo data could not be loaded. Please reload the page.')));
}

async function render() {
  const mine = ++token;
  let result;
  try {
    result = await build(parse());
  } catch (err) {
    result = { title: 'Something went wrong', el: failure(), shell: { screen: 'missing' } };
  }
  if (mine !== token || !result) return;
  setShell(result.shell);
  main.replaceChildren(result.el);
  document.title = `${result.title} · Fitness Analyst demo`;
  main.scrollTop = 0;
  window.scrollTo(0, 0);
  const target = result.focus ? main.querySelector(result.focus) : null;
  if (target) {
    (target.closest('.turn') ?? target).scrollIntoView({ block: 'start' });
    target.focus({ preventScroll: true });
  } else if (!first) {
    const heading = main.querySelector('[data-focus]');
    if (heading) heading.focus({ preventScroll: true });
  }
  first = false;
}

async function start() {
  initExplain();
  try {
    const [tree, manifest] = await Promise.all([getJSON('/api/tree'), getJSON('/api/manifest')]);
    ctx = { tree, manifest };
    setNotice(manifest);
  } catch (err) {
    setShell({ screen: 'missing' });
    main.replaceChildren(failure());
    return;
  }
  window.addEventListener('hashchange', render);
  render();
}

start();
