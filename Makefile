.PHONY: help install install-dev clean test test-cov lint format type-check run run-demo validate-config docs clean-pyc clean-test

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make install-dev   - Install development dependencies"
	@echo "  make test         - Run tests"
	@echo "  make test-cov     - Run tests with coverage"
	@echo "  make lint         - Run all linting tools"
	@echo "  make format       - Format code with black and isort"
	@echo "  make type-check   - Run mypy type checking"
	@echo "  make run          - Run the application"
	@echo "  make run-demo     - Run the threaded runner demo"
	@echo "  make clean        - Clean all generated files"
	@echo "  make docs         - Generate documentation (placeholder)"

# Installation targets
install:
	pip install --upgrade pip setuptools wheel
	pip install -r requirements.txt

install-dev: install
	pip install -e ".[dev]"

# Testing targets
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

# Code quality targets
lint: type-check
	flake8 src/ tests/ --max-line-length=88 --extend-ignore=E203,W503
	pylint src/ --exit-zero

format:
	black src/ tests/
	isort src/ tests/

type-check:
	mypy src/ --ignore-missing-imports

# Running targets
run:
	python src/main.py

run-demo:
	python src/examples/threaded_runner_demo.py

# Validation targets
validate-config:
	@python -c "from src.config_validator import validate_configuration_files; \
	from pathlib import Path; \
	result = validate_configuration_files(Path('config.yaml'), Path('environment.yaml')); \
	print('Configuration is valid!' if result else 'Configuration has errors!')"

# Documentation targets
docs:
	@echo "Documentation generation not yet implemented"
	@echo "TODO: Add Sphinx documentation"

# Cleaning targets
clean: clean-pyc clean-test
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .mypy_cache/
	rm -rf .pytest_cache/

clean-pyc:
	find . -type f -name '*.py[co]' -delete
	find . -type d -name '__pycache__' -delete

clean-test:
	rm -rf htmlcov/
	rm -f .coverage
	rm -f coverage.xml
	rm -rf .pytest_cache/

# Development workflow shortcuts
check: format lint test
	@echo "All checks passed!"

# CI simulation
ci: clean check
	@echo "CI simulation complete!" 