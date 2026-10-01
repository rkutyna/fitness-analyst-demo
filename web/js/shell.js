// The frame around every screen: the standing notice, the strip saying who
// you are viewing, the tab bar, and the explanation panel (a side panel on a
// wide screen, a sheet behind the info button on a narrow one).
import { h } from './dom.js';
import { icon } from './icons.js';
import { fmtDay, splitLabel } from './format.js';
import { renderExplain } from './explain.js';

export const TABS = [['today', 'Today'], ['week', 'Week'], ['chat', 'Chat'], ['reports', 'Reports']];

const el = (id) => document.getElementById(id);
const wide = () => matchMedia('(min-width: 900px)').matches;

/** The standing notice: the data's last day, and a flag on a stub-model build. */
export function setNotice(manifest) {
  document.querySelectorAll('.asof').forEach((node) => { node.textContent = fmtDay(manifest.end_date, true); });
  document.querySelectorAll('.dry-run').forEach((node) => { node.hidden = !manifest.dry_run; });
}

function strip(person, goal, screen) {
  if (!person || !goal) {
    return [
      h('a', { class: 'brand', href: '#/', 'aria-label': 'Fitness Analyst demo, home' }, icon('mark', 'icon brand-mark'), h('span', null, 'Fitness Analyst ', h('span', { class: 'brand-sub' }, 'demo'))),
      h('a', { class: 'strip-link', href: '#/about', 'aria-current': screen === 'about' ? 'page' : null }, 'About'),
    ];
  }
  const { name } = splitLabel(person.label);
  return [
    h('p', { class: 'viewing' }, h('span', { class: 'sr-only' }, 'Viewing as '), h('strong', null, name), ' · ', goal.label),
    h('a', { class: 'strip-link', href: '#/' }, 'Switch', h('span', { class: 'sr-only' }, ' person')),
  ];
}

function tabbar(base, active) {
  return TABS.map(([key, text]) => h('a', {
    class: 'tab', href: `${base}/${key}`, 'aria-current': key === active ? 'page' : null,
  }, icon(key, 'icon tab-icon'), h('span', null, text)));
}

/** Redraw the chrome for a route. `tab` is the active tab, or null to hide
 *  the tab bar (landing, person, onboarding, about). */
export function setShell({ person = null, goal = null, tab = null, screen }) {
  el('who').replaceChildren(...strip(person, goal, screen));
  const bar = el('tabbar');
  bar.hidden = !tab;
  el('phone').classList.toggle('has-tabs', Boolean(tab));
  bar.replaceChildren(...(tab ? tabbar(`#/p/${person.id}/g/${goal.id}`, tab) : []));
  renderExplain(el('explain-body'), screen);
}

/** The info button and the sheet it opens on a narrow screen. On a wide one
 *  the panel is always in view and the button is not shown. */
export function initExplain() {
  const panel = el('explain');
  const open = el('explain-open');
  const close = el('explain-close');
  const phone = el('phone');
  const show = (on) => {
    panel.classList.toggle('is-open', on);
    open.setAttribute('aria-expanded', String(on));
    phone.inert = on && !wide();
    if (on) {
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-modal', 'true');
      close.focus();
    } else {
      panel.removeAttribute('role');
      panel.removeAttribute('aria-modal');
    }
  };
  open.addEventListener('click', () => show(true));
  close.addEventListener('click', () => { show(false); open.focus(); });
  panel.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && panel.classList.contains('is-open')) { show(false); open.focus(); }
  });
  // A link inside the sheet navigates: close it so the new screen is in view.
  panel.addEventListener('click', (event) => {
    if (event.target.closest('a[href^="#/"]') && panel.classList.contains('is-open')) show(false);
  });
  matchMedia('(min-width: 900px)').addEventListener('change', () => show(false));
}
