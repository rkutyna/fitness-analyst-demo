// Inline SVG icons, drawn here: no icon font, no external request. Each is a
// 24x24 stroke drawing that takes its colour from the text around it.
import { s } from './dom.js';

const PATHS = {
  today: ['M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8z', 'M12 2.5v2.5', 'M12 19v2.5', 'M2.5 12H5', 'M19 12h2.5',
    'M5.3 5.3l1.8 1.8', 'M16.9 16.9l1.8 1.8', 'M5.3 18.7l1.8-1.8', 'M16.9 7.1l1.8-1.8'],
  week: ['M4 6.5h16v13H4z', 'M4 10h16', 'M8 4v3.5', 'M16 4v3.5', 'M7.5 13.5h2', 'M11 13.5h2', 'M14.5 13.5h2', 'M7.5 16.5h2', 'M11 16.5h2'],
  chat: ['M4 5h11v8H9l-3 2.6V13H4z', 'M17 9h3v8h-2v2.4L15.2 17H11v-2'],
  reports: ['M6 3.5h9l3 3V20.5H6z', 'M9 8h5', 'M9 11h3', 'M14.5 13a2.5 2.5 0 1 0 0 5a2.5 2.5 0 0 0 0-5z', 'M16.4 17.2l1.9 1.9'],
  rest: ['M15.5 4.5a7.5 7.5 0 1 0 4.5 12.3A6.5 6.5 0 0 1 15.5 4.5z', 'M17.5 6h3l-3 3.5h3'],
  notyet: ['M4 6.5h16v13H4z', 'M4 10h16', 'M8 4v3.5', 'M16 4v3.5'],
  chevron: ['M9 6l6 6l-6 6'],
  down: ['M6 9l6 6l6-6'],
  back: ['M15 6l-6 6l6 6'],
  info: ['M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18z', 'M12 11v5.5', 'M12 7.6v.4'],
  close: ['M6 6l12 12', 'M18 6L6 18'],
  replay: ['M5 12a7 7 0 1 0 2.2-5.1', 'M4.5 4.5v3.2h3.2'],
  mark: ['M3 17l5-6l4 3l5-8l4 5'],
};

export function icon(name, cls = 'icon') {
  return s('svg', { class: cls, viewBox: '0 0 24 24', width: '24', height: '24', 'aria-hidden': 'true', focusable: 'false' },
    (PATHS[name] ?? []).map((d) => s('path', { d })));
}
