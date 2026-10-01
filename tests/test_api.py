import shutil

import pytest
from fastapi.testclient import TestClient

from app.bundle_schema import QA, Interview, Manifest, Overview, Plan, Tree
from app.main import create_app

from .conftest import BUNDLE, WEB, tree_routes


def test_health_and_ready(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    ready = client.get("/readyz")
    assert ready.status_code == 200 and ready.json()["status"] == "ready"


def test_manifest_and_tree(client):
    manifest = Manifest.model_validate(client.get("/api/manifest").json())
    tree = Tree.model_validate(client.get("/api/tree").json())
    assert manifest.end_date == tree.end_date
    assert len(tree.people) == 4


def test_person_routes(client, tree):
    for person in tree["people"]:
        overview = Overview.model_validate(client.get(f"/api/people/{person['id']}/overview").json())
        assert overview.person_id == person["id"] and overview.series
        qa = QA.model_validate(client.get(f"/api/people/{person['id']}/qa").json())
        assert qa.scope == "person" and qa.id == person["id"] and qa.answers


def test_goal_routes(client, tree):
    for person in tree["people"]:
        for goal in person["goals"]:
            gid = goal["id"]
            assert Interview.model_validate(client.get(f"/api/goals/{gid}/interview").json()).goal_id == gid
            assert Plan.model_validate(client.get(f"/api/goals/{gid}/plan").json()).goal_id == gid
            qa = QA.model_validate(client.get(f"/api/goals/{gid}/qa").json())
            assert qa.scope == "goal" and qa.id == gid


def test_walk_the_whole_tree(client, tree):
    routes = tree_routes(tree)
    assert len(routes) == 4 * 2 + 12 * 3
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, route
        assert response.headers["content-type"].startswith("application/json"), route
        assert response.json(), route


@pytest.mark.parametrize("path", [
    "/api/people/Z/overview", "/api/people/Z/qa", "/api/people/AA/overview",
    "/api/goals/Z9/interview", "/api/goals/Z9/plan", "/api/goals/Z9/qa",
    "/api/goals/A/plan", "/api/people/A1/overview",
    "/api/nothing", "/api/people/A/other", "/api",
])
def test_unknown_ids_are_404(client, path):
    assert client.get(path).status_code == 404


def test_traversal_is_404(client):
    for path in ("/api/people/..%2f..%2fmanifest/overview", "/..%2fapp/main.py",
                 "/%2e%2e/app/main.py", "/js/../../app/main.py"):
        response = client.get(path)
        assert response.status_code in (200, 404)
        assert b"create_app" not in response.content


def test_no_write_routes(client):
    for method in ("post", "put", "patch", "delete"):
        for path in ("/api/tree", "/api/people/A/overview", "/api/goals/A1/plan", "/"):
            assert getattr(client, method)(path).status_code in (404, 405), (method, path)


def test_no_cookies(client, tree):
    for route in ["/", "/api/tree", "/api/manifest", *tree_routes(tree)]:
        assert "set-cookie" not in client.get(route).headers


def test_etag_and_conditional_get(client):
    first = client.get("/api/tree")
    etag = first.headers["etag"]
    assert etag
    assert first.headers["cache-control"] == "public, max-age=300"
    second = client.get("/api/tree", headers={"If-None-Match": etag})
    assert second.status_code == 304 and second.content == b""
    assert second.headers["etag"] == etag
    assert client.get("/api/tree", headers={"If-None-Match": '"other"'}).status_code == 200


def test_gzip(client):
    response = client.get("/api/goals/A1/interview", headers={"Accept-Encoding": "gzip"})
    assert response.headers["content-encoding"] == "gzip"
    assert response.json()["goal_id"] == "A1"


def test_static_frontend_and_spa_fallback(client):
    root = client.get("/")
    assert root.status_code == 200 and root.headers["content-type"].startswith("text/html")
    assert "text/javascript" in client.get("/js/main.js").headers["content-type"]
    assert "text/css" in client.get("/css/style.css").headers["content-type"]
    for route in ("/p/A", "/p/A/g/A1/plan", "/about"):
        page = client.get(route)
        assert page.status_code == 200 and page.text == root.text
    assert client.get("/js/nope.js").status_code == 404
    assert client.get("/nope.png").status_code == 404


def test_docs_endpoints_disabled(client):
    shell = client.get("/").text
    # /docs and /redoc are client routes (the app shell); the schema file is gone.
    assert client.get("/docs").text == shell and client.get("/redoc").text == shell
    assert client.get("/openapi.json").status_code == 404


def test_readyz_before_load_is_503():
    app = create_app(bundle_dir=BUNDLE, web_dir=WEB)
    # No lifespan run: the app has not loaded its bundle.
    response = TestClient(app).get("/readyz")
    assert response.status_code == 503


def test_corrupted_bundle_fails_startup(tmp_path):
    bad = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bad)
    (bad / "goals" / "A1" / "plan.json").write_text('{"goal_id": "A1"}')
    with pytest.raises(RuntimeError, match=r"goals/A1/plan\.json"):
        with TestClient(create_app(bundle_dir=bad, web_dir=WEB)):
            pass


def test_unparseable_and_missing_files_fail_startup(tmp_path):
    bad = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bad)
    (bad / "manifest.json").write_text("{not json")
    (bad / "people" / "B" / "qa.json").unlink()
    with pytest.raises(RuntimeError) as err:
        with TestClient(create_app(bundle_dir=bad, web_dir=WEB)):
            pass
    assert "manifest.json" in str(err.value) and "people/B/qa.json" in str(err.value)


def test_missing_bundle_dir_fails_startup(tmp_path):
    with pytest.raises(RuntimeError, match="invalid"):
        with TestClient(create_app(bundle_dir=tmp_path / "nope", web_dir=WEB)):
            pass


def test_favicon_ico_is_served(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
    assert response.content[:4] == b"\x00\x00\x01\x00"          # an ICO header
    assert client.get("/favicon.svg").status_code == 200
    assert 'href="/favicon.ico"' in client.get("/").text


def test_every_series_carries_a_python_headline(client, tree):
    for person in tree["people"]:
        overview = Overview.model_validate(client.get(f"/api/people/{person['id']}/overview").json())
        for series in overview.series:
            complete = [p for p in series.points if not p.partial and p.value is not None]
            assert series.headline is not None and complete
            assert series.headline.value == complete[-1].value
            assert series.headline.week_start == complete[-1].start
            assert series.headline.display and series.headline.unit == series.unit


def test_answers_carry_plan_flags(client, tree):
    flagged = 0
    for person in tree["people"]:
        for goal in person["goals"]:
            qa = QA.model_validate(client.get(f"/api/goals/{goal['id']}/qa").json())
            for answer in qa.answers:
                flagged += answer.plan_question
                # A fallback carries no facts at all: the model's draft was
                # refused, so only narrated plan answers must carry plan facts.
                if answer.plan_question and answer.mode == "narration":
                    assert answer.has_plan_facts, (goal["id"], answer.question)
        qa = QA.model_validate(client.get(f"/api/people/{person['id']}/qa").json())
        assert not any(a.plan_question for a in qa.answers)
    assert flagged >= 2 * 12 - 2


def test_manifest_is_a_real_run_and_the_public_shape(client):
    manifest = client.get("/api/manifest").json()
    assert manifest["dry_run"] is False
    assert manifest["model"]["model"] and manifest["engine_sha"]
    assert "+dirty" not in manifest["engine_sha"]
    for internal in ("clock_pins", "consumer_sha", "fact_template", "plan_tools_note"):
        assert internal not in client.get("/api/manifest").text


def test_frontend_reads_python_decisions_instead_of_computing_them():
    js = {p.name: p.read_text() for p in WEB.glob("js/*.js")}
    joined = "\n".join(js.values())
    assert "lastFullWeek" not in joined                     # the headline comes from the bundle
    assert "series.headline" in js["reports.js"] and "headline.display" in js["views.js"]
    assert "plan_question" in js["answer.js"] and "has_plan_facts" in js["answer.js"]
    assert "plan_tools_visible" not in joined and "source_tool" not in joined and "tool_name" not in joined
    # No number is rounded, grouped or converted on the way to the screen.
    for reformatting in ("toLocaleString", "Math.round", "toPrecision", "parseFloat", "NumberFormat"):
        assert reformatting not in joined, reformatting
    # The only toFixed calls place marks and axis ticks inside a chart.
    assert all("toFixed" not in text for name, text in js.items() if name != "charts.js")
    # The preview notice exists only for a stub-model manifest.
    assert "!manifest.dry_run" in js["shell.js"]
    assert "Preview build" not in js["about.js"]


def test_about_page_states_who_wrote_what():
    text = (WEB / "js" / "about.js").read_text()
    for needle in ("generated in advance by a language model", "manifest.generated_at", "m.model",
                   "computed by Python", "verified before publishing", "fallback",
                   "Python’s own template text"):
        assert needle in text, needle
