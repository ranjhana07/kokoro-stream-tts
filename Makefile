PYTHON ?= python
IMAGE ?= kokoro-stream-tts

.PHONY: install test run worker loadtest docker-build up down clean

install:
	$(PYTHON) -m pip install -e ".[dev,serve]"

test:
	$(PYTHON) -m pytest -q

run:
	KOKORO_ENGINE=sine $(PYTHON) -m flask --app kokoro_stream.wsgi run --port 8000

worker:
	$(PYTHON) -m kokoro_stream.jobs.worker

loadtest:
	$(PYTHON) -m kokoro_stream.loadtest --streams 25

docker-build:
	docker build -t $(IMAGE) .

up:
	docker compose up --build -d

down:
	docker compose down

clean:
	rm -rf output .pytest_cache build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
