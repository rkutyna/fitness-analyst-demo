"""The frontend's rule, checked by rendering its modules under node: a figure
is wrapped only where its display string appears verbatim, bundle text is never
read as markup, every Today section may refuse, and nothing is recomputed."""
import json
import re

from .conftest import BUNDLE, WEB
from .render import call, needs_node

FIG = '<span class="fig">{}</span>'
# who is speaking, above a message: visible name plus a visually hidden "said:"
YOU_AUTHOR = '<p class="author author-you"><span>You</span><span class="sr-only"> said:</span></p>'
VAULT_AUTHOR = ('<p class="author author-vault"><span class="author-disc" aria-hidden="true">'
                '<svg class="icon author-mark"')


def figures(*displays: str) -> list[dict]:
    return [{"display": d, "unit": None, "label": "a label", "source": "a source"} for d in displays]


# ---- the figure highlighter -----------------------------------------------------------
@needs_node
def test_an_exact_match_is_wrapped_everywhere_it_appears(tmp_path):
    text = "You averaged 61 bpm this week, up from 59 bpm. The median was 61 bpm."
    out = call(tmp_path, "highlight.js", "highlightFigures", text, figures("61 bpm", "59 bpm"))
    assert out.count(FIG.format("61 bpm")) == 2 and out.count(FIG.format("59 bpm")) == 1
    assert re.sub(r"</?span[^>]*>", "", out) == text          # the words are untouched


@needs_node
def test_a_figure_that_is_not_in_the_text_verbatim_leaves_it_alone(tmp_path):
    text = "You averaged about sixty-one beats per minute, roughly 61.0bpm."
    out = call(tmp_path, "highlight.js", "highlightFigures", text, figures("61 bpm", "7 h 23 m", "Sixty-one"))
    assert out == text and "<span" not in out
    assert call(tmp_path, "highlight.js", "highlightFigures", text, []) == text


@needs_node
def test_a_figure_does_not_match_inside_a_longer_number_or_word(tmp_path):
    text = "Week 1 of 12, from Monday, August 31: 10 min, then 1.5 km, then 31 more; week 12b, not 112."
    pieces = json.loads(call(tmp_path, "highlight.js", "splitFigures", text,
                             figures("1", "12", "Monday, August 31"), as_json=True))
    assert "".join(p["text"] for p in pieces) == text
    assert [p["text"] for p in pieces if p["figure"]] == ["1", "12", "Monday, August 31"]


def wrapped(tmp_path, text: str, *displays: str) -> list[str]:
    pieces = json.loads(call(tmp_path, "highlight.js", "splitFigures", text, figures(*displays), as_json=True))
    assert "".join(p["text"] for p in pieces) == text
    return [p["text"] for p in pieces if p["figure"]]


@needs_node
def test_only_figure_sized_strings_are_wrapped(tmp_path):
    # a figure is a string with a digit in it, at most 32 characters long
    assert wrapped(tmp_path, "You ran for 1 h 26 m on Monday, August 31.", "1 h 26 m", "Monday, August 31") \
        == ["1 h 26 m", "Monday, August 31"]
    # a whole Python-composed line is not a figure: it embeds model-written intent text
    line = "Base: Monday, August 31 to Sunday, September 13 (2 weeks)."
    assert len(line) > 32
    text = f"{line} Keep it easy and let the legs settle in."
    assert wrapped(tmp_path, text, line) == []
    # a word with no digit is not a figure
    assert wrapped(tmp_path, "You are in the Base phase, a rest day follows.", "Base", "a rest day", "Rest day") == []
    # and the digit-free word does not stop the figures around it from being wrapped
    assert wrapped(tmp_path, "Base, week 3: 45 min.", "Base", "45 min") == ["45 min"]


@needs_node
def test_the_length_limit_is_32_characters_inclusive(tmp_path):
    at_limit = "1" * 31 + "x"
    over = "1" * 32 + "x"
    assert len(at_limit) == 32 and len(over) == 33
    assert wrapped(tmp_path, f"a {at_limit} b {over} c", at_limit, over) == [at_limit]
    # counted in characters, not UTF-16 units: 32 astral characters with a digit is at the limit
    astral = "1" + "\U0001d7d8" * 31
    assert wrapped(tmp_path, f"a {astral} b", astral) == [astral]


@needs_node
def test_bundle_text_is_never_interpreted_as_html(tmp_path):
    text = 'Pace <img src=x onerror=alert(1)> was 5 < 6 & <b>61 bpm</b>.'
    out = call(tmp_path, "highlight.js", "highlightFigures", text, figures("61 bpm", "<b>61 bpm</b>"))
    assert "<img" not in out and "<b>" not in out
    assert "&lt;img src=x onerror=alert(1)>" in out and "5 &lt; 6 &amp; " in out
    assert FIG.format("&lt;b>61 bpm&lt;/b>") in out      # the longer figure wins, and is escaped
    # exactly the figure span is an element; everything else is text
    assert re.findall(r"<[a-z/][^>]*>", out) == ['<span class="fig">', "</span>"]


# ---- the answer card --------------------------------------------------------------------
def answers(path: str) -> list[dict]:
    return json.loads((BUNDLE / path).read_text())["answers"]


@needs_node
def test_a_narrated_answer_is_serif_with_its_figures_marked_and_its_sources_collapsed(tmp_path):
    answer = next(a for a in answers("people/B/qa.json") if a["mode"] == "narration" and a["figures"])
    out = call(tmp_path, "answer.js", "vaultMessage", answer)
    assert VAULT_AUTHOR in out and '<div class="narration">' in out
    for figure in answer["figures"]:
        shown = figure["display"]
        if shown in answer["text"] and re.search(r"\d", shown) and len(shown) <= 32:
            assert FIG.format(shown) in out
    v = answer["verification"]
    assert f'{FIG.format(v["figures_verified"])} of {FIG.format(v["figures_total"])} figures traced to Python' in out
    assert f'<details class="sources"><summary><span>Sources ({len(answer["sources"])})</span>' in out
    assert "<details open" not in out and 'open=""' not in out
    for fact in answer["facts"]:
        assert f'<td data-label="Value" class="fig">{fact["value"]}</td>' in out


@needs_node
def test_a_fallback_is_not_serif_and_says_what_it_is(tmp_path):
    fallback = next(a for a in answers("goals/A3/qa.json") if a["mode"] == "fallback")
    out = call(tmp_path, "answer.js", "vaultMessage", fallback)
    assert VAULT_AUTHOR in out        # the author above a fallback still reads "Vault"
    assert '<h2 class="card-label is-refuse">Answer withheld</h2>' in out
    assert '<div class="template">' in out and 'class="narration"' not in out
    assert "Python’s own template text" in out and fallback["verification"]["reason"] in out
    assert "No figures stated" in out and "traced to Python" not in out and "Sources (" not in out


def article(out: str) -> str:
    return re.search(r"<article .*</article>", out).group(0)


@needs_node
def test_a_vault_message_has_its_author_and_keeps_its_sources_inside_the_bubble(tmp_path):
    answer = next(a for a in answers("people/B/qa.json") if a["mode"] == "narration" and a["figures"] and a["sources"])
    out = call(tmp_path, "answer.js", "vaultMessage", answer)
    assert out.startswith('<div class="msg msg-vault">' + VAULT_AUTHOR)
    assert '<span>Vault</span><span class="sr-only"> said:</span></p>' in out
    bubble = article(out)
    assert 'class="bubble bubble-vault answer is-narration"' in bubble
    # the traced line and the Sources disclosure live in the bubble's footer, under the hairline
    foot = re.search(r'<div class="answer-foot">.*</div></article>', bubble).group(0)
    assert "figures traced to Python" in foot and '<details class="sources">' in foot
    assert out.endswith("</article></div>")            # nothing of the message sits outside the bubble


@needs_node
def test_bundle_text_in_a_vault_message_stays_inert(tmp_path):
    answer = dict(next(a for a in answers("people/B/qa.json") if a["mode"] == "narration"),
                  text='5 < 6 <img src=x onerror=alert(1)> and <b>bold</b>')
    out = call(tmp_path, "answer.js", "vaultMessage", answer)
    assert "<img" not in out and "<b>" not in out and "5 &lt; 6 &lt;img src=x" in out


def chat_out(tmp_path, gid: str, pid: str, initial, question: str | None = None) -> str:
    goal_qa = json.loads((BUNDLE / "goals" / gid / "qa.json").read_text())
    person_qa = json.loads((BUNDLE / "people" / pid / "qa.json").read_text())
    if question is not None:
        goal_qa["answers"][initial]["question"] = question
    return call(tmp_path, "chat.js", "chatView", goal_qa, person_qa, {"gid": gid, "base": "#/x", "initial": initial})


@needs_node
def test_the_thread_is_a_log_of_two_sided_messages_with_authors(tmp_path):
    out = chat_out(tmp_path, "B1", "B", 0)
    first = answers("goals/B1/qa.json")[0]
    assert '<ol class="transcript" role="log" aria-live="polite" aria-label="Conversation">' in out
    # the vault speaks first, then the turn: your question on the right, its answer on the left
    intro = out.index('<li class="turn intro">')
    turn = out.index('<li class="turn" id="turn-0">')
    assert intro < turn
    assert out.index("Ask the vault") < turn and VAULT_AUTHOR in out[intro:turn]
    item = out[turn:]
    you = item.index('<div class="msg msg-you">' + YOU_AUTHOR)
    vault = item.index('<div class="msg msg-vault">' + VAULT_AUTHOR)
    assert you < vault
    assert f'<div class="bubble bubble-you"><p class="question" tabindex="-1">{first["question"]}</p></div>' in item
    assert "Sources (" in item[vault:] and "Sources (" not in item[:vault]
    # suggestions are buttons to send, with no leading bullet
    assert '<button type="button" class="suggestion"><span>' in out and 'class="dot"' not in out


@needs_node
def test_a_fallback_answer_in_the_thread_is_still_withheld_and_labelled(tmp_path):
    out = chat_out(tmp_path, "A3", "A", 0)
    assert answers("goals/A3/qa.json")[0]["mode"] == "fallback"
    item = out[out.index('<li class="turn" id="turn-0">'):]
    assert YOU_AUTHOR in item and VAULT_AUTHOR in item
    assert '<h2 class="card-label is-refuse">Answer withheld</h2>' in item and "Sources (" not in item


@needs_node
def test_a_question_with_markup_in_it_is_inert_in_the_thread(tmp_path):
    out = chat_out(tmp_path, "B1", "B", 0, question="Is 5 < 6? <img src=x onerror=alert(1)>")
    assert "<img" not in out and "Is 5 &lt; 6? &lt;img src=x onerror=alert(1)>" in out


def test_the_waiting_beat_is_three_dots_with_hidden_words_and_no_beat_when_reduced():
    chat = (WEB / "js" / "chat.js").read_text()
    assert "h('i'), h('i'), h('i')" in chat and "Waiting for the vault…" in chat
    assert "reducedMotion()) reveal()" in chat                        # reduced motion: no wait at all
    assert re.search(r"\.beat i \{[^}]*animation: beat", (WEB / "css" / "style.css").read_text())


def test_the_user_bubble_text_reaches_contrast_4_5_on_its_fill():
    css = (WEB / "css" / "style.css").read_text()
    tokens = dict(re.findall(r"--([a-z-]+): (#[0-9A-Fa-f]{6});", css))
    assert re.search(r"\.bubble-you \{[^}]*background: var\(--attention-line\); color: var\(--ink\)", css)
    assert tokens["attention-line"].upper() == "#2E3450"

    def lum(hex_):
        chans = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    hi, lo = sorted((lum(tokens["ink"]), lum(tokens["attention-line"])), reverse=True)
    assert (hi + 0.05) / (lo + 0.05) >= 4.5


# ---- today ------------------------------------------------------------------------------
def real_today(gid: str) -> dict:
    """The goal's real `today.json` from the bundle, the very file the site serves."""
    return json.loads((BUNDLE / "goals" / gid / "today.json").read_text())


def fixture_day(gid: str, date: str) -> dict:
    today = real_today(gid)
    return next(d for d in today["days"] if d["date"] == date)


@needs_node
def test_today_prints_display_strings_and_the_band(tmp_path):
    day = fixture_day("A1", "2026-08-31")
    out = call(tmp_path, "today.js", "dayCards", day)
    readiness = day["readiness"]
    assert f'<span class="big-figure fig">{readiness["score"]["display"]}</span>' in out
    assert f'class="band-chip band-{readiness["band"]}"' in out and out.count("<i></i>") == 3
    for part in ("hrv", "rhr"):
        assert f'<dd class="metric-value fig">{readiness["components"][part]["display"]}</dd>' in out
    session = day["plan"]["sessions"][0]
    assert f'<h2 class="card-label">{session["label"]}</h2>' in out
    assert f'<p class="card-title">{session["title"]}</p>' in out
    # the raw values never reach the screen, only Python's display strings
    assert str(readiness["components"]["hrv"]["value"]) not in out
    assert call(tmp_path, "today.js", "freshnessLine", day) == \
        '<p class="freshness">2026-08-31 · data through 2026-08-31</p>'


@needs_node
def test_every_today_section_can_refuse(tmp_path):
    refusal = {"status": "unavailable", "reason": "stale",
               "detail": "Readiness needs recent recovery data.", "remedy": "Wear the watch overnight."}
    day = {"date": "2026-09-02", "plan": dict(refusal, detail="No plan covers this week.", remedy=None),
           "readiness": refusal, "yesterday": {"status": "empty", "reason": "rest_day", "detail": None},
           "something_new": {"ignored": True}}
    out = call(tmp_path, "today.js", "dayCards", day)
    assert out.count('class="card refusal"') == 3
    assert '<p class="refusal-detail">No plan covers this week.</p>' in out
    assert '<p class="remedy">Wear the watch overnight.</p>' in out and out.count('class="remedy"') == 1
    assert '<p class="refusal-detail">Not available right now.</p>' in out      # no detail was sent
    assert "fault" not in out and "something_new" not in out and "null" not in out


@needs_node
def test_a_rest_day_a_graded_day_and_a_day_that_has_not_happened(tmp_path):
    rest = call(tmp_path, "today.js", "dayCards", fixture_day("B1", "2026-08-31"))
    assert '<p class="rest-marker is-heading">' in rest and "Rest day</p>" in rest
    assert "Rest day.</p>" not in rest                                # the title only repeated it
    graded = fixture_day("A1", "2026-09-01")
    out = call(tmp_path, "today.js", "dayCards", graded, {"titles": {"plan": "Session", "yesterday": "The day before"}})
    assert '<h2 class="card-label">The day before</h2>' in out and '<p class="card-title">Swapped</p>' in out
    assert "Substituted: Traditional strength training" in out
    for figure in ("duration_min", "avg_heart_rate"):
        assert f'<dd class="fig">{graded["yesterday"]["workouts"][0][figure]["display"]}</dd>' in out
    planned = call(tmp_path, "today.js", "dayCards", graded, {"planOnly": True})
    assert "Readiness" not in planned and "Yesterday" not in planned and "35 minutes" in planned


@needs_node
def test_a_section_the_screen_cannot_read_is_a_fault_not_a_refusal(tmp_path):
    day = {"date": "2026-09-02", "plan": {"status": "ok"}, "readiness": None, "yesterday": {"status": "ok", "outcome": "done"}}
    out = call(tmp_path, "today.js", "dayCards", day)
    assert out.count('class="card fault"') == 2 and "could not read" in out
    assert '<p class="card-title">Done</p>' in out


@needs_node
def test_today_picks_the_flagged_day_and_falls_back_to_as_of(tmp_path):
    today = real_today("B1")
    picked = json.loads(call(tmp_path, "today.js", "pickToday", today, as_json=True))
    assert picked["date"] == today["as_of"] and picked["is_today"] is True
    for day in today["days"]:
        del day["is_today"]
    assert json.loads(call(tmp_path, "today.js", "pickToday", today, as_json=True))["date"] == today["as_of"]
    assert call(tmp_path, "today.js", "pickToday", {"as_of": "2026-08-31", "days": []}, as_json=True) == "null"


# ---- the shell ----------------------------------------------------------------------------
def test_the_notice_is_in_the_page_before_any_script_runs():
    html = (WEB / "index.html").read_text()
    notices = re.findall(r"Synthetic people · pre-generated · data as of <span class=\"asof\">[^<]*</span> · no model runs on this site", html)
    assert len(notices) == 2            # in the phone, and in the sheet that covers it on a narrow screen
    assert 'aria-controls="explain"' in html and 'id="tabbar"' in html and 'content="dark"' in html


def test_the_tabs_are_the_apps_in_the_apps_order():
    shell = (WEB / "js" / "shell.js").read_text()
    assert "[['today', 'Today'], ['week', 'Week'], ['chat', 'Chat'], ['reports', 'Reports']]" in shell
    assert "'aria-current': key === active ? 'page' : null" in shell
    main = (WEB / "js" / "main.js").read_text()
    for needle in ("'welcome', 'today', 'week', 'reports'", "get('q')", "hashchange", "sessionStorage", "catch"):
        assert needle in main, needle


def test_the_stylesheet_carries_the_apps_tokens_and_is_dark_only():
    css = (WEB / "css" / "style.css").read_text()
    for token, value in {"--ground": "#101219", "--surface": "#232734", "--line": "#2E3341", "--ink": "#E4E3EA",
                         "--ink-secondary": "#A3A3B4", "--ink-tertiary": "#767889", "--accent": "#9DA9DC",
                         "--figure": "#E8DCD2", "--refuse": "#868799", "--fault": "#D89A96",
                         "--band-recover": "#9D7FC8", "--band-steady": "#8497CB", "--band-strong": "#86D8AE"}.items():
        assert f"{token}: {value};" in css, token
    assert "color-scheme: dark;" in css and "prefers-color-scheme" not in css
    assert "prefers-reduced-motion: reduce" in css and "text-transform: uppercase" in css
    assert "url(" not in css and "@import" not in css          # nothing is fetched from anywhere


def test_no_module_reaches_outside_this_origin():
    for path in WEB.rglob("*.js"):
        text = path.read_text()
        assert "fetch('http" not in text and "import('http" not in text, path
        assert not re.search(r"from\s+['\"]https?:", text), path


# ---- the pushed-screen header and the scroll container ---------------------------------
def _rule(css: str, selector: str) -> str:
    m = re.search(r"(?m)^" + re.escape(selector) + r" \{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


def first_run(tmp_path, goal: str, mutate=None) -> str:
    interview = json.loads((BUNDLE / "goals" / goal / "interview.json").read_text())
    if mutate:
        mutate(interview)
    return call(tmp_path, "firstrun.js", "firstRunView", interview, {}, {"base": f"#/p/{goal[0]}/g/{goal}"})


@needs_node
def test_the_onboarding_cards_print_the_display_strings_exactly_as_given(tmp_path):
    d1, b1 = first_run(tmp_path, "D1"), first_run(tmp_path, "B1")
    assert FIG.format("± 1 h 10 m") in d1 and FIG.format("180 days") in d1
    assert FIG.format("12 weeks") in d1 and FIG.format("4 weeks") in d1 and "None recorded" in d1
    assert FIG.format("± 40 m") in b1 and FIG.format("46.3 min") in b1
    assert FIG.format("95.5 min") in b1 and FIG.format("109.7 min") in b1 and FIG.format("72") in b1
    # the frontend neither re-rounds, re-units nor reads the raw value
    for raw in ("1.161", "0.673"):
        assert raw not in d1 + b1
    assert "180 days days" not in d1 and "min min" not in b1 and "weeks weeks" not in d1 + b1
    # the mini bar chart's words are the display strings too
    assert 'aria-label="Weekly values: 86 min, 82.7 min, 103.7 min, 109.7 min"' in b1


@needs_node
def test_a_card_without_display_says_not_available_and_prints_no_raw_figure(tmp_path):
    def drop(interview):
        for turn in interview["transcript"]:
            if turn.get("card"):
                turn["card"].pop("display", None)

    for goal in ("D1", "B1"):
        out = first_run(tmp_path, goal, drop)
        cards = "".join(re.findall(r'<section class="card computed">.*?</section>', out))   # the coach's prose has its own figures
        assert "not available" in cards
        for raw in ("1.161", "0.673", "46.3", "109.7", "180", "103.7", "12<", ">4<"):
            assert raw not in cards, (goal, raw)
        assert "None recorded" in first_run(tmp_path, "D1", drop)     # non-numeric content survives
        assert "Check-in day: Sunday." in out


def test_the_header_is_a_grid_so_a_title_and_its_button_cannot_overlap():
    css = (WEB / "css" / "style.css").read_text()
    bar, title = _rule(css, ".nav-bar"), _rule(css, ".nav-title")
    assert "display: grid" in bar and "grid-template-columns: 44px minmax(0, 1fr) 44px" in bar
    # the title owns a column and shrinks with an ellipsis; it is never taken out of the flow
    assert "grid-column: 2" in title and "min-width: 0" in title and "text-overflow: ellipsis" in title
    assert "position: absolute" not in title and "translateX" not in title
    # the wide action leaves the centring: title left, action right, each its own column
    assert "minmax(0, 1fr) auto" in _rule(css, ".nav-bar.is-split")
    assert "min-height: 44px" in _rule(css, ".nav-action")        # the tap target


@needs_node
def test_the_welcome_header_is_the_split_one_and_the_others_are_centred(tmp_path):
    out = call(tmp_path, "firstrun.js", "firstRunView", {"transcript": []}, {}, {"base": "#/p/D/g/D1"})
    assert '<header class="nav-bar is-split"><h1 class="nav-title"' in out
    assert 'class="pill nav-action"' in out and "Skip to the app" in out
    briefs = call(tmp_path, "briefs.js", "briefsDayView", {"entries": []}, "2026-08-31", "#/p/B/g/B1")
    assert '<header class="nav-bar"><a class="back"' in briefs and "is-split" not in briefs


def test_the_scroll_container_has_a_quiet_scrollbar_with_a_stable_gutter():
    css = (WEB / "css" / "style.css").read_text()
    assert "scrollbar-width: thin; scrollbar-color: var(--line) transparent;" in css
    assert "scrollbar-gutter: stable" in _rule(css, ".screen")
    assert "::-webkit-scrollbar-thumb" in css and "overflow-y: auto" in _rule(css, ".screen")
