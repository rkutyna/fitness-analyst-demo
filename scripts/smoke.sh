#!/usr/bin/env bash
# Build the image, run it, and fetch every route in the tree. Exits non-zero on
# any failure and always removes the container.
set -euo pipefail

cd "$(dirname "$0")/.."
IMAGE="${IMAGE:-fitness-analyst-demo:smoke}"
NAME="fitness-analyst-demo-smoke-$$"
PORT="${SMOKE_PORT:-18080}"
BASE="http://127.0.0.1:${PORT}"
START=$(date +%s)
FAILS=0

BODY=$(mktemp)
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -f "$BODY"; }
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; FAILS=$((FAILS + 1)); }

echo "==> building $IMAGE"
docker build -q -t "$IMAGE" . >/dev/null

echo "==> starting on $BASE"
docker run -d --name "$NAME" -p "127.0.0.1:${PORT}:8080" "$IMAGE" >/dev/null

echo "==> waiting for /readyz"
ready=0
for _ in $(seq 1 60); do
  if curl -fsS "$BASE/readyz" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [ "$ready" != 1 ]; then
  docker logs "$NAME" >&2 || true
  echo "FAIL: /readyz never became ready" >&2
  exit 1
fi

curl -fsS "$BASE/healthz" >/dev/null || fail "/healthz"

echo "==> fetching every route in the tree"
TREE=$(curl -fsS "$BASE/api/tree")
ROUTES=$(printf '%s' "$TREE" | python3 -c '
import json, sys
tree = json.load(sys.stdin)
routes = ["/api/manifest", "/api/tree"]
for p in tree["people"]:
    routes += [f"/api/people/{p['"'"'id'"'"']}/overview", f"/api/people/{p['"'"'id'"'"']}/qa"]
    for g in p["goals"]:
        routes += [f"/api/goals/{g['"'"'id'"'"']}/{leaf}" for leaf in ("interview", "plan", "qa")]
print("\n".join(routes))
')
COUNT=0
while IFS= read -r route; do
  [ -n "$route" ] || continue
  code=$(curl -s -o "$BODY" -w '%{http_code} %{content_type}' "$BASE$route")
  case "$code" in
    "200 application/json"*) python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$BODY" \
        || fail "$route: body is not JSON" ;;
    *) fail "$route: got '$code'" ;;
  esac
  COUNT=$((COUNT + 1))
done <<< "$ROUTES"

echo "==> app shell, client routes, unknown ids, headers"
ctype=$(curl -s -o /dev/null -w '%{content_type}' "$BASE/")
case "$ctype" in text/html*) ;; *) fail "/ is not HTML ($ctype)" ;; esac
curl -fsS "$BASE/" | grep -q '<script type="module" src="/js/main.js">' || fail "/ is missing the app script"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/p/A/g/A1/plan")" = 200 ] || fail "SPA fallback"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/js/main.js")" = 200 ] || fail "/js/main.js"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/css/style.css")" = 200 ] || fail "/css/style.css"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/people/Z/overview")" = 404 ] || fail "unknown person should 404"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/goals/Z9/plan")" = 404 ] || fail "unknown goal should 404"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/goals/Z9/briefs")" = 404 ] || fail "unknown goal's briefs should 404"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/people/A/briefs")" = 404 ] || fail "the old per-person briefs route should be gone"
# The two optional per-goal files: present is 200, absent is 404, never anything else.
for route in /api/goals/A1/today /api/goals/A1/briefs; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE$route")
  case "$code" in 200|404) ;; *) fail "$route: optional route answered $code" ;; esac
done
for file in /js/shell.js /js/today.js /js/chat.js /js/highlight.js /js/briefs.js; do
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE$file")" = 200 ] || fail "$file"
done
curl -sI "$BASE/api/tree" | tr -d '\r' | grep -qi "^content-security-policy:.*frame-ancestors 'none'" || fail "CSP header"

echo "==> container is non-root and healthy"
[ "$(docker exec "$NAME" id -u)" != 0 ] || fail "container runs as root"
for _ in $(seq 1 20); do
  status=$(docker inspect -f '{{.State.Health.Status}}' "$NAME")
  [ "$status" = healthy ] && break
  sleep 2
done
[ "$status" = healthy ] || fail "HEALTHCHECK status is '$status'"

SIZE=$(docker image inspect "$IMAGE" --format '{{.Size}}' | awk '{printf "%.0f MB", $1/1000000}')
ELAPSED=$(( $(date +%s) - START ))
if [ "$FAILS" -ne 0 ]; then
  echo "SMOKE FAILED: $FAILS problem(s)" >&2
  exit 1
fi
echo "SMOKE OK: $COUNT routes, image $SIZE, ${ELAPSED}s"
