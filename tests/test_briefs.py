"""The daily briefs, checked by rendering the frontend modules under node: the
narration under the day on Today (serif, its figures marked, a fallback shown
as Python's own text), the whole brief in the day view opened from Reports, and
the rule that nothing in a brief is read as markup, parsed or recomputed."""
import copy
import html
import json
import re

from .conftest import BUNDLE, WEB
from .render import call, needs_node

FIG = '<span class="fig">{}</span>'
GOALS = [path.parent.name for path in sorted(BUNDLE.glob("goals/*/briefs.json"))]


def real_briefs(gid: str) -> dict:
    """The goal's real `briefs.json`, the very file the site serves."""
    return json.loads((BUNDLE / "goals" / gid / "briefs.json").read_text())


def real_entry(gid: str = "B3") -> dict:
    return real_briefs(gid)["entries"][0]


def fallback_of(entry: dict) -> dict:
    """A fallback built from a real entry in the test; `bundle/` is not touched."""
    fallback = copy.deepcopy(entry)
    fallback["mode"] = "fallback"
    fallback["verification"].update(ok=False, reason="a figure was not in the facts", figures_verified=0)
    return fallback


# ---- "Written ..." --------------------------------------------------------------------------
@needs_node
def test_written_at_is_rearranged_as_text_and_never_converted(tmp_path):
    def line(raw):
        return call(tmp_path, "briefs.js", "writtenLine", raw)

    assert line("2026-08-31T05:00:00+00:00") == "Written 31 Aug 2026 at 05:00 UTC"
    assert line("2026-09-05T21:07:33Z") == "Written 5 Sep 2026 at 21:07 UTC"
    # an offset is named, never applied: the day and the hour are the stored ones
    assert line("2026-12-31T23:30:00-08:00") == "Written 31 Dec 2026 at 23:30 -08:00"
    assert line("2026-08-31T05:00:00.250+02:00") == "Written 31 Aug 2026 at 05:00 +02:00"
    assert line("2026-08-31 05:00") == "Written 31 Aug 2026 at 05:00"
    # what is not an instant is shown as it arrived, and an empty value is said to be empty
    assert line("yesterday evening") == "Written yesterday evening"
    assert line("2026-13-01T05:00:00Z") == "Written 2026-13-01T05:00:00Z"
    assert line("") == "The vault did not say when this was written."


def test_the_timestamp_code_does_no_date_arithmetic():
    code = (WEB / "js" / "briefs.js").read_text()
    assert "new Date" not in code and "Date." not in code and "Intl" not in code and "getTime" not in code
    assert "innerHTML" not in code


# ---- which brief Today shows --------------------------------------------------------------------
@needs_node
def test_today_picks_the_evening_narration_else_the_morning_one_for_that_day_only(tmp_path):
    morning = real_entry()
    evening = dict(copy.deepcopy(morning), kind="evening", label="Evening brief", narration="How the day went.")
    other_day = dict(copy.deepcopy(morning), date="2026-09-01", label="Morning brief", narration="Another day.")
    silent = dict(copy.deepcopy(morning), kind="evening", label="Evening brief", narration=None)

    def pick(entries, date="2026-08-31"):
        return json.loads(call(tmp_path, "briefs.js", "pickBrief", {"as_of": "2026-08-31", "entries": entries}, date, as_json=True))

    assert pick([morning, evening, other_day])["label"] == "Evening brief"
    assert pick([morning, silent])["label"] == "Morning brief"            # an evening with no narration is not shown
    assert pick([morning, other_day], "2026-09-01")["narration"] == "Another day."
    assert pick([morning], "2026-09-02") is None                          # no brief for that day, no card
    assert pick([silent]) is None
    assert call(tmp_path, "briefs.js", "pickBrief", None, "2026-08-31", as_json=True) == "null"


def test_only_the_pinned_days_today_screen_carries_the_brief():
    main = (WEB / "js" / "main.js").read_text()
    assert "pickBrief(briefs, day.date)" in main and "briefCard(briefs, day)" in main
    week = (WEB / "js" / "week.js").read_text()
    assert "brief" not in week.lower()          # the day opened from the Week tab has no brief


# ---- the card on Today -----------------------------------------------------------------------------
@needs_node
def test_a_narrated_brief_on_today_is_serif_with_its_figures_marked(tmp_path):
    entry = real_entry()
    out = call(tmp_path, "briefs.js", "todayBriefCard", entry)
    assert out.startswith('<section class="card brief"><h2 class="card-label">Morning brief</h2>')
    assert "The coach's own words · Written 31 Aug 2026 at 05:00 UTC" in out
    assert '<div class="narration">' in out and 'class="template"' not in out and "Python’s own" not in out
    # the closing paragraph only: not the facts block above it
    assert "Today's session" not in out and "•" not in out
    assert out.count(FIG.format("3")) == 3 and out.count(FIG.format("10")) == 1 and out.count(FIG.format("8")) == 2
    assert re.sub(r"</?span[^>]*>", "", re.search(r'<div class="narration">(.*)</div>', out).group(1)) == \
        f'<p>{entry["narration"]}</p>'


@needs_node
def test_a_fallback_brief_on_today_is_pythons_text_and_says_so(tmp_path):
    entry = fallback_of(real_entry())
    out = call(tmp_path, "briefs.js", "todayBriefCard", entry)
    assert "The coach's own words" not in out and "coach" not in out.lower()
    assert '<h2 class="card-label is-refuse">Morning brief</h2>' in out
    assert "Python’s own text · Written 31 Aug 2026 at 05:00 UTC" in out
    assert '<div class="template">' in out and 'class="narration"' not in out
    assert "<span" not in out                                       # nothing is marked as a verified figure
    assert "Python’s own template text, shown because the model’s draft failed verification." in out
    assert "The verifier said: a figure was not in the facts." in out


@needs_node
def test_brief_text_is_never_read_as_markup(tmp_path):
    entry = dict(real_entry(), narration="Run 3 < 4 <img src=x onerror=alert(1)> and <b>3</b>.")
    out = call(tmp_path, "briefs.js", "todayBriefCard", entry)
    assert "<img" not in out and "<b>" not in out
    assert f"Run {FIG.format('3')} &lt; 4 &lt;img src=x onerror=alert(1)> and &lt;b>{FIG.format('3')}&lt;/b>." in out
    assert set(re.findall(r"<([a-z0-9]+)", out)) == {"section", "h2", "p", "div", "span"}


# ---- the Reports slot and the day view ---------------------------------------------------------
@needs_node
def test_reports_has_the_daily_briefs_entry_only_for_a_goal_that_has_briefs(tmp_path):
    overview = json.loads((BUNDLE / "people" / "B" / "overview.json").read_text())
    out = call(tmp_path, "reports.js", "reportsView", overview, real_briefs("B3"), "#/p/B/g/B3")
    assert 'data-slot="briefs"' in out
    assert 'href="#/p/B/g/B3/reports/briefs/2026-08-31"' in out
    assert ">Daily briefs</span>" in out and "The morning and evening briefs, day by day." in out
    assert out.index("Data overview") < out.index("Daily briefs")
    bare = call(tmp_path, "reports.js", "reportsView", overview, None, "#/p/B/g/B3")
    assert "Daily briefs" not in bare and "data-slot" not in bare and "Data overview" in bare
    empty = call(tmp_path, "reports.js", "reportsView", overview, {"as_of": "2026-08-31", "entries": []}, "#/p/B/g/B3")
    assert "Daily briefs" not in empty


@needs_node
def test_the_day_view_lists_the_dates_entries_with_the_full_text_and_collapsed_sources(tmp_path):
    briefs = real_briefs("B3")
    entry = briefs["entries"][0]
    out = call(tmp_path, "briefs.js", "briefsDayView", briefs, "2026-08-31", "#/p/B/g/B3")
    assert 'class="back" href="#/p/B/g/B3/reports"' in out and '<h1 class="nav-title"' in out
    assert '<h2 class="card-label">Morning brief</h2>' in out
    assert '<p class="chrome brief-provenance">Written 31 Aug 2026 at 05:00 UTC</p>' in out
    # the facts block is sans with hanging bullets; the narration is serif and keeps its marked figures
    facts_head = entry["text"][: -len(entry["narration"])]
    assert '<div class="brief-facts">' in out and '<div class="narration">' in out
    assert "Today's session — Full Body Strength A (strength):" in out and facts_head.startswith("Today's session")
    assert '<span class="brief-marker marker-dot" aria-hidden="true">•</span><span class="brief-text">3 × 10 Goblet squat</span>' in out
    assert out.index("brief-facts") < out.index('class="narration"')
    assert FIG.format("10") in out
    # under the hairline: the traced line and the collapsed Sources row with the facts table
    v = entry["verification"]
    assert f'{FIG.format(v["figures_verified"])} of {FIG.format(v["figures_total"])} figures traced to Python' in out
    assert f'<details class="sources"><summary><span>Sources ({len(entry["facts"])})</span>' in out
    assert "<details open" not in out and 'open=""' not in out
    for fact in entry["facts"]:
        assert f'<td data-label="Value" class="fig">{fact["value"]}</td>' in out
    assert out.index('class="answer-foot"') > out.index('class="narration"')


@needs_node
def test_the_day_view_sets_state_marked_lines_and_keeps_the_text_whole(tmp_path):
    entry = copy.deepcopy(real_entry())
    facts = "Yesterday:\n✓ Easy run 30 min\n✗ Strength session\n• A very long line that goes on and on and on so that it wraps beside its glyph"
    entry["text"] = f"{facts}\n\n{entry['narration']}"
    out = call(tmp_path, "briefs.js", "briefsDayView", {"as_of": entry["date"], "entries": [entry]}, entry["date"], "#/x")
    assert '<p class="brief-line">Yesterday:</p>' in out
    assert 'marker-done" aria-hidden="true">✓</span><span class="sr-only">Done. </span><span class="brief-text">Easy run 30 min</span>' in out
    assert 'marker-missed" aria-hidden="true">✗</span><span class="sr-only">Not done. </span><span class="brief-text">Strength session</span>' in out
    assert "A very long line that goes on and on and on so that it wraps beside its glyph</span>" in out
    # every word of the stored text reaches the screen, in order (the screen-reader words aside)
    shown = re.sub(r'<span class="sr-only">[^<]*</span>', "", out)
    shown = re.sub(r'<span class="fig">([^<]*)</span>', r"\1", shown)
    shown = html.unescape(re.sub(r"<[^>]+>", " ", shown))
    assert " ".join(entry["text"].split()) in " ".join(shown.split())


@needs_node
def test_markup_in_a_brief_is_inert_in_the_day_view(tmp_path):
    entry = copy.deepcopy(real_entry())
    entry["text"] = "• 5 < 6 <img src=x onerror=alert(1)>\n✓ <b>bold</b> & more\n\n" + entry["narration"]
    entry["facts"][0] = dict(entry["facts"][0], label="<i>day</i>", value="<script>x</script>", source="<u>s</u>")
    out = call(tmp_path, "briefs.js", "briefsDayView", {"as_of": entry["date"], "entries": [entry]}, entry["date"], "#/x")
    for tag in ("<img", "<b>", "<i>", "<script", "<u>"):
        assert tag not in out
    assert "5 &lt; 6 &lt;img src=x onerror=alert(1)>" in out and "&lt;b>bold&lt;/b> &amp; more" in out
    assert "&lt;script>x&lt;/script>" in out
    # the day view's DOM is the module's own elements and nothing else
    assert set(re.findall(r"<([a-z0-9]+)", out)) <= {
        "div", "header", "a", "svg", "path", "span", "h1", "section", "h2", "p", "details", "summary", "table",
        "caption", "thead", "tr", "th", "tbody", "td"}


@needs_node
def test_a_fallback_in_the_day_view_is_python_only_and_not_marked(tmp_path):
    entry = fallback_of(real_entry())
    out = call(tmp_path, "briefs.js", "briefsDayView", {"as_of": entry["date"], "entries": [entry]}, entry["date"], "#/x")
    assert 'class="narration"' not in out and out.count('<div class="template">') == 1
    assert '<h2 class="card-label is-refuse">Morning brief</h2>' in out
    assert FIG.format("10") not in out and "No figures stated" in out and "traced to Python" not in out
    assert "Python’s own template text" in out and "Sources (" in out       # the facts are still Python's, and shown


@needs_node
def test_a_date_without_briefs_says_so(tmp_path):
    out = call(tmp_path, "briefs.js", "briefsDayView", real_briefs("B3"), "2026-09-09", "#/p/B/g/B3")
    assert "There are no briefs for 2026-09-09." in out and 'class="card refusal"' in out


@needs_node
def test_every_real_brief_renders_in_both_places(tmp_path):
    for gid in GOALS:
        briefs = real_briefs(gid)
        for entry in briefs["entries"]:
            card = call(tmp_path, "briefs.js", "todayBriefCard", entry)
            assert f'<h2 class="card-label">{entry["label"]}</h2>' in card, gid
            day = call(tmp_path, "briefs.js", "briefsDayView", briefs, entry["date"], f"#/p/x/g/{gid}")
            assert "<details" in day and "Written " in day, gid
    assert len(GOALS) == 12


# ---- the app route and the explanation panel ------------------------------------------------------------
def test_the_briefs_day_view_has_its_own_route_and_back_goes_to_reports():
    main = (WEB / "js" / "main.js").read_text()
    assert "parts.length === 7 && tab === 'reports' && parts[5] === 'briefs' && ISO_DAY.test(parts[6])" in main
    assert "case 'briefs':" in main and "screen: 'briefs'" in main and "tab: 'reports'" in main
    assert "/api/people/${person.id}/briefs" not in main               # briefs are per goal now


def test_the_explanation_panel_says_the_brief_is_the_only_model_written_text():
    text = (WEB / "js" / "explain.js").read_text()
    today = re.search(r"today: \['Today', \[(.*?)\]\],\n  week:", text, re.S).group(1)
    assert "only text on this screen that a model wrote" in today
    assert "checked against the facts Python published" in today
    briefs = re.search(r"briefs: \['Daily briefs', \[(.*?)\]\],\n  about:", text, re.S).group(1)
    assert "facts block is written by Python" in briefs and "the one part the model wrote" in briefs
    for sentences in (today, briefs):
        assert "!" not in sentences
