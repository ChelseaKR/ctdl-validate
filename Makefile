# make verify reproduces the full merge-blocking gate set locally, byte for
# byte with CI: ci.yml runs this exact target, and release.yml re-runs it at
# the tagged commit before anything publishes. Run it before opening a PR.
.PHONY: verify sync lint format typecheck test audit clean

verify: sync lint format typecheck test audit
	@echo "make verify: all gates passed."

sync:
	# `--frozen` installs a stale lock and exits 0, so it cannot gate drift.
	# `uv lock --check` and `uv sync --locked` both exit 1 on drift; keep the
	# explicit check ahead of the install so the failure names the cause (CQ-09).
	uv lock --check
	uv sync --locked

lint:
	uv run ruff check .

format:
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest --cov --cov-report=term-missing

# Dependency vulnerability audit over the locked environment. The project has
# zero runtime dependencies, so this audits the locked dev toolchain; the
# local package itself is not on PyPI and is reported as skipped, not failed.
audit:
	uv run pip-audit

clean:
	rm -rf .coverage .pytest_cache .mypy_cache .ruff_cache dist build
