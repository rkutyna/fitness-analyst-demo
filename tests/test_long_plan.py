"""The long plan on the Week tab: the bundle carries it, the API serves it, and
the frontend shows a collapsible card titled "Week N of M · phase" that holds
every week, the current one marked and past ones dimmed, and nothing at all
when a goal has none."""
import json
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.bundle_schema import Plan
from app.main import create_app

from .conftest import BUNDLE, WEB
from .render import call, needs_node

ROOT = Path(__file__).resolve().parent.parent
PHASES = ["Base", "Base", "Build", "Recovery", "Build", "Build", "Peak", "Taper"]
KEY_SESSIONS = {"Base": "Easy (run)", "Build": "Long (run)", "Recovery": "Recovery (walk)",
                "Peak": "Intervals (run)", "Taper": "Easy (run)"}


def long_plan(current: int = 1, start: str = "2026-08-31") -> dict:
    """A well-formed long plan: week 1 is `start`, then consecutive seven-day weeks."""
    first = date.fromisoformat(start)
    weeks = []
    for index, phase in enumerate(PHASES, start=1):
        begin = first + timedelta(days=7 * (index - 1))
        weeks.append({
            "index": index, "start": begin.isoformat(),
            "end": (begin + timedelta(days=6)).isoformat(), "withheld": False,
            "phase_label": phase, "intent": f"Intent sentence for week {index}.",
            "key_session_label": KEY_SESSIONS[phase],
            "is_current": index == current, "is_past": index < current})
    return {"as_of": start, "weeks_total": len(weeks), "current_index": current,
            "position_label": f"Week {current} of {len(weeks)}", "weeks": weeks}


def with_long_plan(tmp_path: Path, gid: str = "A1", **kwargs) -> Path:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    for path in (bundle / "goals").glob("*/plan.json"):
        plan = json.loads(path.read_text())
        # the one goal gets this long plan; every other goal has none, whatever
        # bundle (a regenerated one carries them for all) these tests ran on
        plan["long_plan"] = long_plan(**kwargs) if path.parent.name == gid else None
        path.write_text(json.dumps(plan))
    return bundle


# ---- the API ----------------------------------------------------------------------
def test_the_api_serves_the_long_plan_and_only_for_the_goal_that_has_one(tmp_path):
    bundle = with_long_plan(tmp_path)
    with TestClient(create_app(bundle_dir=bundle, web_dir=WEB)) as client:
        plan = Plan.model_validate(client.get("/api/goals/A1/plan").json())
        assert plan.long_plan.position_label == "Week 1 of 8"
        assert [w.index for w in plan.long_plan.weeks] == list(range(1, 9))
        assert [w.is_current for w in plan.long_plan.weeks][:2] == [True, False]
        other = client.get("/api/goals/A2/plan").json()
        assert other["long_plan"] is None


def test_a_bundle_without_long_plans_still_loads(client):
    assert Plan.model_validate(client.get("/api/goals/A1/plan").json()).goal_id == "A1"


def test_an_internal_field_in_a_long_plan_fails_startup(tmp_path):
    bundle = with_long_plan(tmp_path)
    path = bundle / "goals" / "A1" / "plan.json"
    plan = json.loads(path.read_text())
    plan["long_plan"]["fingerprint"] = "abc123"
    path.write_text(json.dumps(plan))
    with pytest.raises(RuntimeError, match=r"goals/A1/plan\.json"):
        with TestClient(create_app(bundle_dir=bundle, web_dir=WEB)):
            pass


# ---- the frontend ------------------------------------------------------------------
def plan_with(long: dict | None) -> dict:
    plan = json.loads((BUNDLE / "goals" / "A1" / "plan.json").read_text())
    plan["long_plan"] = long
    return plan


def week_tab(tmp_path: Path, plan: dict) -> str:
    return call(tmp_path, "week.js", "weekView", plan, "#/p/A/g/A1")


def hidden_rows(out: str) -> int:
    return len(re.findall(r'<li class="lp-week[^"]*"[^>]* hidden=""', out))


@needs_node
def test_the_week_tab_shows_the_position_every_week_and_the_current_one(tmp_path):
    out = week_tab(tmp_path, plan_with(long_plan(current=1)))
    assert '<span class="card-title">Week 1 of 8 · Base</span>' in out
    assert out.count('class="lp-week') == 8
    for index in range(1, 9):
        assert f'<span class="lp-index">Week {index}</span>' in out
        assert f"Intent sentence for week {index}." in out
    assert "Aug 31 – Sep 6" in out or "Aug 31 – Sept 6" in out      # the dates, from the bundle
    assert out.count("is-current") == 1 and out.count('aria-current="step"') == 1
    assert "is-past" not in out
    assert "Key session: Long (run)" in out and "This week" in out
    assert "The weeks ahead" not in out                              # the old outline is replaced


@needs_node
def test_the_card_starts_collapsed_on_the_current_week(tmp_path):
    out = week_tab(tmp_path, plan_with(long_plan(current=4)))
    assert 'aria-expanded="false"' in out and 'aria-controls="lp-' in out
    assert hidden_rows(out) == 7                                     # every week but the current one
    current = re.search(r'<li class="lp-week is-current"[^>]*>', out).group(0)
    assert "hidden" not in current
    opened = call(tmp_path, "plan.js", "longPlanCard", long_plan(current=4), {"expanded": True})
    assert 'aria-expanded="true"' in opened and hidden_rows(opened) == 0


@needs_node
def test_past_weeks_are_dimmed_and_the_heading_follows_the_current_week(tmp_path):
    out = week_tab(tmp_path, plan_with(long_plan(current=4)))
    assert "Week 4 of 8 · Recovery</span>" in out
    assert out.count("is-past") == 3 and out.count("is-current") == 1
    # the three past weeks come first, then the current one
    assert out.index("is-past") < out.index("is-current")


@needs_node
def test_a_withheld_week_shows_no_text_and_no_phase(tmp_path):
    long = long_plan()
    long["weeks"][2].update(withheld=True, phase_label=None, intent=None, key_session_label=None)
    out = week_tab(tmp_path, plan_with(long))
    assert "Not available" in out
    assert "Intent sentence for week 3." not in out and "None" not in out and "null" not in out


@needs_node
def test_no_long_plan_means_no_long_plan_view(tmp_path):
    out = week_tab(tmp_path, plan_with(None))
    assert "lp-toggle" not in out and "lp-week" not in out
    assert "The weeks ahead" in out                                  # the old outline remains


@needs_node
def test_the_week_tab_keeps_the_days_and_what_the_plan_carries(tmp_path):
    plan = json.loads((BUNDLE / "goals" / "B1" / "plan.json").read_text())
    plan["rejected"] = ["A later week named an amount Python did not compute."]
    out = week_tab(tmp_path, plan)
    for day in plan["week"]["days"]:
        assert f'href="#/p/A/g/A1/week/{day["date"]}"' in out
        assert f'<span class="weekday">{day["weekday"]}</span>' in out
    assert out.count("Rest day</p>") == sum(d["is_rest_day"] for d in plan["week"]["days"])
    assert "Worth knowing" in out and plan["warnings"][0][:30] in out
    assert "Could not be written" in out and plan["rejected"][0] in out
    assert "Passed the plan checks" in out


@needs_node
def test_onboarding_shows_the_drafted_plan_with_every_week_open(tmp_path):
    out = call(tmp_path, "plan.js", "longPlanDraft", long_plan(current=1))
    assert "Your 8-week plan" in out and out.count('class="lp-week') == 8 and "hidden" not in out


def test_the_stylesheet_styles_the_long_plan_states():
    css = (WEB / "css" / "style.css").read_text()
    for selector in (".lp-week.is-current", ".lp-week.is-past", ".long-plan-list", ".lp-now"):
        assert selector in css


def test_the_frontend_does_not_compute_the_position():
    js = (WEB / "js" / "plan.js").read_text()
    assert "position_label" in js and "is_current" in js and "is_past" in js
    assert "weeks_total" in js
    # no arithmetic on indices or dates: the label and flags come from the bundle
    assert "index +" not in js and "index -" not in js and "Date.now" not in js
