from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "bundle"
WEB = ROOT / "web"


@pytest.fixture(scope="session")
def client():
    app = create_app(bundle_dir=BUNDLE, web_dir=WEB)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def tree(client):
    return client.get("/api/tree").json()


def tree_routes(tree: dict) -> list[str]:
    routes = []
    for person in tree["people"]:
        routes += [f"/api/people/{person['id']}/overview", f"/api/people/{person['id']}/qa"]
        for goal in person["goals"]:
            routes += [f"/api/goals/{goal['id']}/{leaf}" for leaf in ("interview", "plan", "qa")]
    return routes
