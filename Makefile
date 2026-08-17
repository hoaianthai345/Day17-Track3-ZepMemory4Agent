.PHONY: up down build smoke seed demo student baseline compare test short local agent sessions episodes heartbeat compiled forget golden ui presentation report student-report golden-report clean

build:
	docker compose build

up:
	docker compose up -d redis qdrant

down:
	docker compose down

smoke:
	docker compose run --rm app python -m src.smoke

seed:
	docker compose run --rm app python -m src.seed

demo:
	docker compose run --rm app python -m src.evaluate --impl reference --reuse-seeded

student:
	docker compose run --rm app python -m src.evaluate --impl student --reuse-seeded

baseline:
	docker compose run --rm app python -m src.evaluate --impl no_memory

compare:
	docker compose run --rm app python -m src.compare_reports

test:
	docker compose run --rm app pytest -q

short:
	docker compose run --rm app python -m src.demo_short_term

local:
	docker compose run --rm app python -m src.local_baseline

agent:
	docker compose run --rm app python -m src.demo_agent --impl reference --reset

sessions:
	docker compose run --rm app python -m src.demo_sessions

episodes:
	docker compose run --rm app python -m src.episodic_maintenance

heartbeat:
	docker compose run --rm app python -m src.heartbeat --dry-run

compiled:
	docker compose run --rm app python -m src.compiled_kb --reset

forget:
	docker compose run --rm app python -m src.forget --user-id minh-lab17

golden:
	docker compose run --rm app python -m src.evaluate --impl student --reuse-seeded --golden

ui:
	docker compose run --rm --service-ports -e PYTHONPATH=/workspace app streamlit run src/demo_ui.py --server.address 0.0.0.0 --server.port 8501

presentation:
	python3 -m http.server 8502 --bind 127.0.0.1

# Build colorful HTML reports from every reports/*benchmark*.json (+ run log if present).
report:
	docker compose run --rm app python -m src.report_html --all --log reports/run.log

# Run the student benchmark, capture the run log, then render the HTML report.
student-report:
	docker compose run --rm app sh -c "python -m src.evaluate --impl student --reuse-seeded 2>&1 | tee reports/run.log && python -m src.report_html --input reports/benchmark.json --log reports/run.log"

# Run the golden benchmark, capture the run log, then render the HTML report.
golden-report:
	docker compose run --rm app sh -c "python -m src.evaluate --impl student --reuse-seeded --golden 2>&1 | tee reports/run.log && python -m src.report_html --input reports/golden_benchmark.json --log reports/run.log"

clean:
	docker compose down -v
	rm -f reports/benchmark*.json reports/benchmark*.md reports/comparison.md reports/golden* reports/*.html reports/run.log
