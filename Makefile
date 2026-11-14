# Universal AI GIS Studio — Makefile
# Cross-platform commands for development and deployment

.PHONY: help install install-base install-mcp install-opencv install-dev install-all test test-unit test-integration lint format type-check clean build release docs

# Default target
help:
	@echo "Universal AI GIS Studio — Available Commands"
	@echo ""
	@echo "Installation:"
	@echo "  make install        Install base dependencies"
	@echo "  make install-mcp    Install MCP server dependencies"
	@echo "  make install-opencv Install OpenCV dependencies"
	@echo "  make install-dev    Install development dependencies"
	@echo "  make install-all    Install all dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-integration Run integration tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run ruff linter"
	@echo "  make format         Format with ruff and black"
	@echo "  make type-check     Run mypy type checker"
	@echo ""
	@echo "Development:"
	@echo "  make run-mcp-stdio  Run MCP server (stdio transport)"
	@echo "  make run-mcp-http   Run MCP server (streamable-http transport)"
	@echo "  make run-bridge     Run QGIS Bridge server"
	@echo "  make run-tests      Run test suite with coverage"
	@echo ""
	@echo "Build & Release:"
	@echo "  make build          Build package (wheel + sdist)"
	@echo "  make release        Build and create GitHub release"
	@echo "  make clean          Clean build artifacts"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs           Build documentation"
	@echo "  make docs-serve     Serve documentation locally"

# =============================================================================
# Installation
# =============================================================================

install:
	pip install --upgrade pip
	pip install -r requirements/base.txt

install-mcp:
	pip install -r requirements/mcp.txt

install-opencv:
	pip install -r requirements/opencv.txt

install-dev:
	pip install -r requirements/dev.txt

install-all:
	pip install -r requirements.txt

# Convenience: install with pip extras
install-pip:
	pip install -e .
install-mcp-pip:
	pip install -e .[mcp]
install-opencv-pip:
	pip install -e .[opencv]
install-dev-pip:
	pip install -e .[dev]
install-all-pip:
	pip install -e .[mcp,opencv,dev]

# =============================================================================
# Testing
# =============================================================================

test:
	python -m pytest tests/ -v --tb=short

test-unit:
	python -m pytest tests/unit/ -v --tb=short

test-integration:
	python -m pytest tests/integration/ -v --tb=short

test-coverage:
	python -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# =============================================================================
# Code Quality
# =============================================================================

lint:
	ruff check .

format:
	ruff check --fix .
	black .
	isort .

type-check:
	mypy .

# =============================================================================
# Development Servers
# =============================================================================

# Run MCP server with stdio transport (for OpenCode, Codex, etc.)
run-mcp-stdio:
	python -m mcp_server.main --transport stdio

# Run MCP server with Streamable HTTP transport
run-mcp-http:
	python -m mcp_server.main --transport streamable-http --port 8766

# Run QGIS Bridge server (requires QGIS)
run-bridge:
	python -m bridge.bridge_server_async

# Run all tests with coverage
run-tests:
	python -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html

# =============================================================================
# Build & Release
# =============================================================================

build:
	python -m build

clean:
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/

release: clean build
	@echo "Ready to publish! Run: twine upload dist/*"

# =============================================================================
# Documentation
# =============================================================================

docs:
	@echo "Building documentation..."
	@mkdir -p docs/_build
	@echo "Docs available in docs/ directory"

docs-serve:
	@echo "Starting docs server at http://localhost:8000"
	@python -m http.server 8000 -d docs/

# =============================================================================
# Docker (optional)
# =============================================================================

docker-build:
	docker build -t universal-ai-gis-studio:latest .

docker-run:
	docker run -it --rm -p 8765:8765 -p 8766:8766 -p 8767:8767 \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/logs:/app/logs \
		universal-ai-gis-studio:latest

# =============================================================================
# QGIS Plugin
# =============================================================================

plugin-install:
	@echo "Installing QGIS plugin..."
	@mkdir -p "$(APPDATA)/QGIS/QGIS3/profiles/default/python/plugins/universal_ai_gis"
	cp -r plugin/universal_ai_gis/* "$(APPDATA)/QGIS/QGIS3/profiles/default/python/plugins/universal_ai_gis/"
	@echo "Plugin installed. Restart QGIS and enable in Plugin Manager."

plugin-zip:
	cd plugin && zip -r ../release/universal_ai_gis_plugin.zip universal_ai_gis -x "*/__pycache__/*" "*/.git*"

# =============================================================================
# Database
# =============================================================================

db-migrate:
	python -c "from database.schema import run_migrations; run_migrations()"

db-reset:
	rm -f data/uagis.db
	@make db-migrate

# =============================================================================
# Default target
# =============================================================================

.DEFAULT_GOAL := help