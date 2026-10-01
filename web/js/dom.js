// Tiny DOM helpers. Everything is built with createElement and text nodes,
// never by parsing HTML strings, so bundle text is never read as markup.
const SVG_NS = 'http://www.w3.org/2000/svg';

function apply(el, attrs) {
  if (!attrs) return;
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith('aria-')) {
      if (value != null) el.setAttribute(key, String(value));
    } else if (value == null || value === false) {
      continue;
    } else if (key === 'class') {
      el.setAttribute('class', value);
    } else if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2), value);
    } else if (value === true) {
      el.setAttribute(key, '');
    } else {
      el.setAttribute(key, String(value));
    }
  }
}

function append(el, kids) {
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
}

export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  apply(el, attrs);
  append(el, kids);
  return el;
}

export function s(tag, attrs, ...kids) {
  const el = document.createElementNS(SVG_NS, tag);
  apply(el, attrs);
  append(el, kids);
  return el;
}

let uid = 0;
export function nextId(prefix) {
  uid += 1;
  return `${prefix}-${uid}`;
}
