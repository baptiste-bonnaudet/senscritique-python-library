.DEFAULT_GOAL := help
.PHONY: help install sync lint format typecheck test test-integration check release clean

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

release: ## Cut a release (usage: make release version=0.2.0)
	@set -e; \
	if [ -z "$(version)" ]; then echo "Error: version is required. Usage: make release version=0.2.0" >&2; exit 1; fi; \
	echo "$(version)" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$' || { echo "Error: version must look like X.Y.Z (e.g. 0.2.0)." >&2; exit 1; }; \
	current_branch="$$(git rev-parse --abbrev-ref HEAD)"; \
	if [ "$$current_branch" != "main" ]; then echo "Error: releases must be cut from 'main' (currently on '$$current_branch')." >&2; exit 1; fi; \
	if [ -n "$$(git status --porcelain)" ]; then echo "Error: working tree is not clean. Commit or stash changes first." >&2; exit 1; fi; \
	if git rev-parse -q --verify "refs/tags/v$(version)" >/dev/null; then echo "Error: tag 'v$(version)' already exists." >&2; exit 1; fi; \
	current_version="$$(grep -m1 '^version = ' pyproject.toml | sed -E 's/^version = "(.*)"$$/\1/')"; \
	if [ "$$current_version" = "$(version)" ]; then echo "Error: pyproject.toml is already at version $(version)." >&2; exit 1; fi; \
	sed -i.bak -E 's/^version = ".*"/version = "$(version)"/' pyproject.toml && rm -f pyproject.toml.bak; \
	uv lock; \
	git add pyproject.toml uv.lock; \
	git commit -m "chore: release v$(version)"; \
	git tag -a "v$(version)" -m "v$(version)"; \
	git push origin HEAD "v$(version)"

clean: ## Remove caches and build artifacts
	rm -rf .venv .ruff_cache .mypy_cache .pytest_cache .tox .eggs \
		htmlcov .coverage coverage.xml dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
