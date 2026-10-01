// Read-only client for the bundle API. Responses are cached in memory for the
// life of the page; the server sends ETags for everything else.
const cache = new Map();

export function getJSON(path) {
  if (!cache.has(path)) {
    const request = fetch(path, { headers: { Accept: 'application/json' } })
      .then((res) => {
        if (!res.ok) {
          const err = new Error(`${path}: ${res.status}`);
          err.status = res.status;
          throw err;
        }
        return res.json();
      })
      .catch((err) => {
        cache.delete(path);
        throw err;
      });
    cache.set(path, request);
  }
  return cache.get(path);
}

/** An optional bundle file: its JSON, or null when the bundle has none (404). */
const absent = new Set();
export async function getOptional(path) {
  if (absent.has(path)) return null;
  try {
    return await getJSON(path);
  } catch (err) {
    if (err.status !== 404) throw err;
    absent.add(path);
    return null;
  }
}
