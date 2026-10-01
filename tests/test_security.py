import re

from .conftest import BUNDLE, WEB, tree_routes

FORBIDDEN = ["health.db",
             "health_coach.", "health_advisor.", "_now", "+dirty", "coach_tools",
             "tool_trace", "clock_pins", "summarize_metric", "get_week_plan", "get_weekly_series"]
# Generic shapes of private infrastructure, checked in every served file: a
# user's home path, a Linux home path, an IPv4 address, an email address. The
# names of private hosts are not listed here (this repo is public); the private
# generator's export gate scans for them before a bundle ever reaches this tree.
PRIVATE_SHAPES = {
    "a /Users/ path": re.compile(r"/Users/"),
    "a /home/ path": re.compile(r"/home/"),
    "an IPv4 address": re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])"),
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def test_security_headers_everywhere(client, tree):
    paths = ["/", "/p/A", "/js/main.js", "/css/style.css", "/healthz", "/readyz",
             "/api/tree", "/api/manifest", "/api/nothing", *tree_routes(tree)[:4]]
    for path in paths:
        headers = client.get(path).headers
        csp = headers["content-security-policy"]
        assert "frame-ancestors 'none'" in csp, path
        assert "default-src 'none'" in csp, path
        assert "script-src 'self'" in csp and "style-src 'self'" in csp, path
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp, path
        assert headers["x-content-type-options"] == "nosniff", path
        assert headers["referrer-policy"], path
        assert headers["x-frame-options"] == "DENY", path


def test_no_inline_script_or_style_in_the_shell(client):
    html = client.get("/").text
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert "<style" not in html and not re.search(r"\sstyle=", html)
    assert not re.search(r"\son[a-z]+=", html)


def test_frontend_sets_no_style_attribute_or_inline_handlers():
    for path in WEB.rglob("*.js"):
        text = path.read_text()
        assert "innerHTML" not in text, path
        assert not re.search(r"""['"]style['"]\s*[:,]""", text), path
        assert ".setAttribute('style'" not in text, path


def _served_files():
    return [p for root in (BUNDLE, WEB) for p in root.rglob("*") if p.is_file()]


def _text(path):
    # The favicon is binary; everything else is text. Undecodable bytes are
    # ignored, so a private string inside a binary file is still found.
    return path.read_bytes().decode("utf-8", "ignore")


def test_served_files_carry_no_private_strings():
    files = _served_files()
    assert len(files) > 40
    for path in files:
        text = _text(path).lower()
        for word in FORBIDDEN:
            assert word not in text, f"{word!r} in {path}"


def test_served_files_carry_no_private_path_address_or_email():
    for path in _served_files():
        text = _text(path)
        for what, shape in PRIVATE_SHAPES.items():
            assert not shape.search(text), f"{what} in {path}"
        assert not EMAIL.search(text), f"an email address in {path}"


def test_the_private_shapes_do_match_what_they_are_for():
    # a scan that cannot fail would pass on every tree
    assert PRIVATE_SHAPES["a /Users/ path"].search("at /Users/someone/x")
    assert PRIVATE_SHAPES["a /home/ path"].search("at /home/someone/x")
    assert PRIVATE_SHAPES["an IPv4 address"].search("host 10.1.2.3:80")
    assert not PRIVATE_SHAPES["an IPv4 address"].search("version 1.2.3 and 2026.08.31 and 1.2.3.4.5")


def test_served_files_carry_no_email_address():
    for path in _served_files():
        assert not EMAIL.search(_text(path)), path


def test_api_responses_carry_no_private_strings(client, tree):
    for route in ["/api/manifest", "/api/tree", *tree_routes(tree)]:
        body = client.get(route).text.lower()
        for word in FORBIDDEN:
            assert word not in body, (word, route)
        assert not EMAIL.search(body), route
