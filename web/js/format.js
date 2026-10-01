// Presentation-only helpers. No figure is derived, rounded or reformatted
// here: a number from the bundle is printed exactly as it arrived (`raw`), and
// only calendar days are given a short display form, as the app does.
const DAY = new Intl.DateTimeFormat('en-US', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const DAY_YEAR = new Intl.DateTimeFormat('en-US', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

export function fmtDay(iso, withYear = false) {
  if (!iso) return '';
  if (!ISO_DAY.test(iso)) return String(iso);
  return (withYear ? DAY_YEAR : DAY).format(new Date(`${iso}T00:00:00Z`));
}

export function fmtTimestamp(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return DAY_YEAR.format(d);
}

export function fmtRange(start, end) {
  if (start === end) return fmtDay(start);
  return `${fmtDay(start)} – ${fmtDay(end)}`;
}

/** A bundle value as text, untouched: no rounding, no grouping. */
export function raw(value) {
  return value == null ? '—' : String(value);
}

export function humanize(key) {
  const text = String(key).replace(/[_-]+/g, ' ').trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function splitLabel(label) {
  const at = label.indexOf(', ');
  if (at < 0) return { name: label, role: '' };
  const role = label.slice(at + 2);
  return { name: label.slice(0, at), role: role.charAt(0).toUpperCase() + role.slice(1) };
}
