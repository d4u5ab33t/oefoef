.PHONY: help install install-dev test lint format type-check clean build docs

help:
	@echo "OIDASHEIM BEAT SYNC — Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install project dependencies"
	@echo "  make install-dev      Install with development tools"
	@echo ""
	@echo "Development:"
	@echo "  make format           Format code with black & isort"
	@echo "  make lint             Check code style with flake8"
	@echo "  make type-check       Run type checking with mypy"
	@echo "  make test             Run tests with pytest"
	@echo "  make test-cov         Run tests with coverage report"
	@echo ""
	@echo "Project:"
	@echo "  make clean            Remove build artifacts & cache"
	@echo "  make build            Build distribution packages"
	@echo "  make run              Run main.py"
	@echo "  make songrid          Generate song grid from HTML files"
	@echo ""

install:
	pip install --upgrade pip setuptools wheel
	pip install -r requirements.txt

install-dev:
	pip install --upgrade pip setuptools wheel
	pip install -e ".[dev]"

format:
	black .
	isort .

lint:
	flake8 . --max-line-length=100 --count --statistics

type-check:
	mypy . --ignore-missing-imports || true

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing

clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage .coverage.*

build: clean
	pip install --upgrade build
	python -m build

run:
	python main.py

songrid:
	python analysis/songrid_builder.py

verify:
	@echo "Running syntax check..."
	python -m py_compile main.py config.py timeline_builder.py audio_analysis.py clip_pool.py db.py
	@echo "✅ All modules verified"

all: clean install-dev lint type-check test build
	@echo "✅ Full pipeline complete!"
