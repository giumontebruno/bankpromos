.PHONY: help install test run api lint clean

help:
	@echo "Bank Promos PY - Makefile"
	@echo ""
	@echo "  make install   - Install dependencies"
	@echo "  make test     - Run tests"
	@echo "  make run      - Run CLI"
	@echo "  make api     - Run API server"
	@echo "  make lint    - Run linter"
	@echo "  make clean   - Clean cache files"

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

run:
	python -m bankpromos list

api:
	uvicorn bankpromos.api:app --reload --port 8000

lint:
	ruff check bankpromos/

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf data/*.db
	rm -rf debug_output/