.PHONY: install test lint typecheck run-scenarios grade-local clean

install:
	pip install -e '.[dev]'

test:
	pytest

lint:
	ruff check src tests

typecheck:
	mypy src

run-scenarios:
	PYTHONPATH=src python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json

grade-local:
	PYTHONPATH=src python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json

run-ui:
	PYTHONPATH=src streamlit run src/langgraph_agent_lab/app.py

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov dist build *.egg-info outputs/*.json
