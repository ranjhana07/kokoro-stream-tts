PYTHON ?= python
IMAGE ?= kokoro-stream-tts
MODEL_DIR ?= models

.PHONY: install test compile run worker loadtest bench report docker-build up down clean

install:
	$(PYTHON) -m pip install -e ".[dev,serve]"

test:
	$(PYTHON) -m pytest -q

compile:
	$(PYTHON) -m compileall -q src tests

run:
	KOKORO_ENGINE=sine $(PYTHON) -m flask --app kokoro_stream.wsgi run --port 8000

worker:
	$(PYTHON) -m kokoro_stream.jobs.worker

loadtest:
	$(PYTHON) -m kokoro_stream.loadtest --streams 25

bench:
	$(PYTHON) -m kokoro_stream.bench --scenario ttfa --prompts short,medium,long --repetitions 3 --model-dir $(MODEL_DIR) --model-file kokoro-v1.0.int8.onnx --name ttfa-local --high-priority

report:
	$(PYTHON) -m kokoro_stream.bench.report benchmarks/results/*.json

docker-build:
	docker build -t $(IMAGE) .

up:
	docker compose up --build -d

down:
	docker compose down

clean:
	rm -rf output .pytest_cache build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
