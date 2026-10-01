"""The two optional per-goal bundle files. `goals/<id>/today.json` and
`goals/<id>/briefs.json` are each validated by `load_bundle` against their
strict model and served from it; a goal without one answers 404, a bundle
without any still loads, and an invalid one stops startup naming the file."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.bundle_schema import Briefs, Today, load_bundle
from app.main import create_app

from .conftest import BUNDLE, WEB

SECTIONS = ("plan", "readiness", "yesterday")
INTERNAL = ("session", "facts", "week_file", "metrics", "workout_key", "phase")


def copy_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    return bundle


def goal_ids(tree: dict) -> list[str]:
    return [goal["id"] for person in tree["people"] for goal in person["goals"]]


def test_every_goal_in_the_bundle_serves_the_file_it_carries(client, tree):
    gids = goal_ids(tree)
    assert len(gids) == 12
    for gid in gids:
        response = client.get(f"/api/goals/{gid}/today")
        assert response.status_code == 200, gid
        assert response.headers["content-type"].startswith("application/json")
        assert response.headers["etag"] and "content-security-policy" in response.headers
        # what is served is the validated model, which is the file, key for key
        assert response.json() == json.loads((BUNDLE / "goals" / gid / "today.json").read_text())
    assert client.get("/api/goals/Z9/today").status_code == 404
    for method in ("post", "put", "delete"):
        assert getattr(client, method)("/api/goals/A1/today").status_code in (404, 405)


def test_the_bundle_loads_it_through_the_schema(tree):
    bundle = load_bundle(BUNDLE)
    assert sorted(bundle.today) == sorted(goal_ids(tree))
    assert all(isinstance(today, Today) for today in bundle.today.values())


def test_a_goal_without_a_today_file_is_404_and_a_bundle_without_any_still_loads(tmp_path, tree):
    bundle = copy_bundle(tmp_path)
    (bundle / "goals" / "A2" / "today.json").unlink()
    with TestClient(create_app(bundle_dir=bundle, web_dir=WEB)) as client:
        assert client.get("/api/goals/A2/today").status_code == 404
        assert client.get("/api/goals/A1/today").status_code == 200
    for path in bundle.glob("goals/*/today.json"):
        path.unlink()
    with TestClient(create_app(bundle_dir=bundle, web_dir=WEB)) as client:
        assert client.get("/readyz").json()["status"] == "ready"
        for gid in goal_ids(tree):
            assert client.get(f"/api/goals/{gid}/today").status_code == 404
            assert client.get(f"/api/goals/{gid}/plan").status_code == 200


def test_every_goal_serves_its_briefs_as_the_file_carries_them(client, tree):
    gids = goal_ids(tree)
    assert len(gids) == 12
    for gid in gids:
        response = client.get(f"/api/goals/{gid}/briefs")
        assert response.status_code == 200, gid
        assert response.headers["content-type"].startswith("application/json")
        assert response.headers["etag"] and "content-security-policy" in response.headers
        assert response.json() == json.loads((BUNDLE / "goals" / gid / "briefs.json").read_text())
        assert response.json()["entries"], gid
    assert client.get("/api/goals/Z9/briefs").status_code == 404
    for method in ("post", "put", "delete"):
        assert getattr(client, method)("/api/goals/A1/briefs").status_code in (404, 405)


def test_the_bundle_loads_briefs_through_the_schema(tree):
    bundle = load_bundle(BUNDLE)
    assert sorted(bundle.briefs) == sorted(goal_ids(tree))
    assert all(isinstance(briefs, Briefs) for briefs in bundle.briefs.values())


def test_a_goal_without_a_briefs_file_is_404_and_the_rest_are_unaffected(tmp_path, tree):
    bundle = copy_bundle(tmp_path)
    (bundle / "goals" / "B3" / "briefs.json").unlink()
    with TestClient(create_app(bundle_dir=bundle, web_dir=WEB)) as served:
        assert served.get("/api/goals/B3/briefs").status_code == 404
        assert served.get("/api/goals/B3/today").status_code == 200
        assert served.get("/api/goals/B2/briefs").status_code == 200
    for path in bundle.glob("goals/*/briefs.json"):
        path.unlink()
    with TestClient(create_app(bundle_dir=bundle, web_dir=WEB)) as served:
        assert served.get("/readyz").json()["status"] == "ready"
        for gid in goal_ids(tree):
            assert served.get(f"/api/goals/{gid}/briefs").status_code == 404


def test_the_per_person_briefs_placeholder_route_is_gone(client, tmp_path, tree):
    for person in tree["people"]:
        assert client.get(f"/api/people/{person['id']}/briefs").status_code == 404
    # even a loose file at the old place is neither read nor served
    bundle = copy_bundle(tmp_path)
    (bundle / "people" / "B" / "briefs.json").write_text('{"anything": []}')
    with TestClient(create_app(bundle_dir=bundle, web_dir=WEB)) as served:
        assert served.get("/api/people/B/briefs").status_code == 404


def mutate(path: Path, change) -> str:
    """The file at `path` with `change` applied to its parsed JSON."""
    raw = json.loads(path.read_text())
    change(raw)
    return json.dumps(raw)


@pytest.mark.parametrize("name,body", [
    ("not json", lambda path: "{not json"),
    ("an array", lambda path: "[]"),
    ("no days", lambda path: mutate(path, lambda d: d.pop("days"))),
    ("no as_of", lambda path: mutate(path, lambda d: d.pop("as_of"))),
    ("an unknown key", lambda path: mutate(path, lambda d: d.update(extra=1))),
    ("an unknown day key", lambda path: mutate(path, lambda d: d["days"][0].update(session={}))),
    ("a bad date", lambda path: mutate(path, lambda d: d["days"][0].update(date="31/08/2026"))),
    ("a figure without its display", lambda path: mutate(path, lambda d: d["days"][0]["readiness"]["score"].pop("display"))),
    ("an unknown section status", lambda path: mutate(path, lambda d: d["days"][0]["plan"].update(status="weird"))),
    ("a refusal without a detail", lambda path: mutate(path, lambda d: d["days"][2]["readiness"].pop("detail"))),
])
def test_an_invalid_today_file_fails_startup(tmp_path, name, body):
    bundle = copy_bundle(tmp_path)
    target = bundle / "goals" / "A1" / "today.json"
    target.write_text(body(target))
    with pytest.raises(RuntimeError, match=r"goals/A1/today\.json"):
        with TestClient(create_app(bundle_dir=bundle, web_dir=WEB)):
            pass


def test_the_real_files_are_in_the_public_shape(tree):
    for gid in goal_ids(tree):
        path = BUNDLE / "goals" / gid / "today.json"
        today = json.loads(path.read_text())
        Today.model_validate(today)                       # strict: unknown keys are errors
        assert sum(day["is_today"] for day in today["days"]) == 1
        for day in today["days"]:
            assert set(day) == {"date", "is_today", "is_future", "freshness", *SECTIONS}
            assert day["is_today"] == (day["date"] == today["as_of"])
            assert day["is_future"] == (day["date"] > today["as_of"])
        text = path.read_text()
        for key in INTERNAL:
            assert f'"{key}"' not in text, (key, gid)


@pytest.mark.parametrize("name,body", [
    ("not json", lambda path: "{not json"),
    ("an array", lambda path: "[]"),
    ("no entries", lambda path: mutate(path, lambda d: d.pop("entries"))),
    ("an unknown key", lambda path: mutate(path, lambda d: d.update(extra=1))),
    ("an unknown entry key", lambda path: mutate(path, lambda d: d["entries"][0].update(created_at="x"))),
    ("a bad mode", lambda path: mutate(path, lambda d: d["entries"][0].update(mode="template"))),
    ("a bad kind", lambda path: mutate(path, lambda d: d["entries"][0].update(kind="noon"))),
    ("a bad date", lambda path: mutate(path, lambda d: d["entries"][0].update(date="31/08/2026"))),
    ("no text", lambda path: mutate(path, lambda d: d["entries"][0].pop("text"))),
    ("a fact without its source", lambda path: mutate(path, lambda d: d["entries"][0]["facts"][0].pop("source"))),
])
def test_an_invalid_briefs_file_fails_startup_and_names_the_file(tmp_path, name, body):
    bundle = copy_bundle(tmp_path)
    target = bundle / "goals" / "B3" / "briefs.json"
    target.write_text(body(target))
    with pytest.raises(RuntimeError, match=r"goals/B3/briefs\.json"):
        with TestClient(create_app(bundle_dir=bundle, web_dir=WEB)):
            pass


def test_the_real_briefs_files_are_in_the_public_shape(tree):
    for gid in goal_ids(tree):
        briefs = json.loads((BUNDLE / "goals" / gid / "briefs.json").read_text())
        Briefs.model_validate(briefs)                      # strict: unknown keys are errors
        today = json.loads((BUNDLE / "goals" / gid / "today.json").read_text())
        assert {e["date"] for e in briefs["entries"]} <= {d["date"] for d in today["days"]}
        for entry in briefs["entries"]:
            if entry["narration"]:
                assert entry["text"].endswith(entry["narration"])      # the closing paragraph
            assert entry["label"] == {"morning": "Morning brief", "evening": "Evening brief"}[entry["kind"]]
