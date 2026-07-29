.DEFAULT_GOAL := help
.PHONY: help install sync lint format typecheck test test-integration check clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'


install: ## Create the virtualenv and install all dependencies
	uv sync

sync: install ## Alias for install

lint: ## Run ruff lint checks
	uv run ruff check .

format: ## Format the codebase with ruff
	uv run ruff format .

typecheck: ## Run mypy
	uv run mypy

test: ## Run the unit test suite
	uv run pytest tests/unit

check: lint typecheck test ## Run lint, type checks and tests

test-integration: ## Run the live integration tests (hits SensCritique)
	uv run pytest tests/integration -m integration --no-cov

clean: ## Remove caches and build artifacts
	rm -rf .venv .ruff_cache .mypy_cache .pytest_cache .tox .eggs \
		htmlcov .coverage coverage.xml dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
