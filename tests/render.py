"""Render a frontend module under node with a tiny DOM stand-in (no browser, no
network). `call` imports `web/js/<module>`, calls `<export>(*args)` and returns
the result: markup for DOM nodes (text escaped as a browser would), JSON for
plain values."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from .conftest import WEB

RENDER = r"""
const [argsPath, jsPath, name] = process.argv.slice(2);
const fs = await import('node:fs');
class Text { constructor(data) { this.nodeType = 3; this.data = data; } }
class El {
  constructor(tag) { this.nodeType = 1; this.tag = tag; this.attrs = {}; this.kids = []; }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return this.attrs[k] ?? null; }
  addEventListener() {}
  querySelector() { return null; }
  remove() {}
  append(...kids) { this.kids.push(...kids.map((k) => (typeof k === 'string' ? new Text(k) : k))); }
}
globalThis.document = { createElement: (t) => new El(t), createElementNS: (n, t) => new El(t),
                        createTextNode: (d) => new Text(d) };
const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const html = (n) => n.nodeType === 3 ? esc(n.data)
  : `<${n.tag}${Object.entries(n.attrs).map(([k, v]) => ` ${k}="${v}"`).join('')}>${n.kids.map(html).join('')}</${n.tag}>`;
const out = (v) => (v == null ? '' : Array.isArray(v) ? v.flat(Infinity).map(out).join('')
  : v.nodeType ? html(v) : typeof v === 'string' ? esc(v) : JSON.stringify(v));
const mod = await import(jsPath);
const args = JSON.parse(fs.readFileSync(argsPath, 'utf8'));
let result = mod[name](...args);
if (result && result.el && result.el.nodeType) result = result.el;   // a view returns { el, ... }
process.stdout.write(process.argv[5] === 'json' ? JSON.stringify(result) : out(result));
"""

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def call(tmp_path: Path, module: str, export: str, *args, as_json: bool = False) -> str:
    args_file = tmp_path / "args.json"
    args_file.write_text(json.dumps(list(args)))
    script = tmp_path / "render.mjs"
    script.write_text(RENDER)
    done = subprocess.run(
        ["node", str(script), str(args_file), (WEB / "js" / module).as_uri(), export,
         "json" if as_json else "html"],
        capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout
