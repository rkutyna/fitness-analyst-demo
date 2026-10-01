PY ?= ./.venv/bin/python
IMAGE ?= fitness-analyst-demo:local

.PHONY: dev test image run smoke

dev:  ## hot-reloading server on :8000 using ./bundle; web/ is re-read per request
	BUNDLE_DIR=bundle CACHE_MAX_AGE=0 WEB_LIVE=1 $(PY) -m uvicorn app.main:app --reload \
		--reload-dir app --port 8000

test:
	$(PY) -m pytest -q

image:
	docker build -t $(IMAGE) .

run: image
	docker run --rm -p 8080:8080 $(IMAGE)

smoke:
	./scripts/smoke.sh
