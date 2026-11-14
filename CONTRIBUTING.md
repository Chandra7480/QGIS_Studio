# Contributing to Universal AI GIS Studio

Thank you for your interest in contributing! This project welcomes contributions from the community.

## 🤝 Ways to Contribute

- **Bug Reports** - Found an issue? Let us know!
- **Feature Requests** - Have an idea? We'd love to hear it.
- **Code Contributions** - Fix bugs, add features, improve performance
- **Documentation** - Improve docs, add examples, fix typos
- **Testing** - Write tests, report bugs, test on different platforms
- **Translations** - Help make the project accessible globally

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- QGIS 4.x (for bridge/plugin development)
- Git
- Docker (optional, for containerized development)

### Development Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/Chandra7480/QGIS_Studio.git
cd QGIS_Studio

# 2. Install development dependencies
make install-dev
# or: pip install -e .[dev]

# 3. Install pre-commit hooks
pre-commit install

# 4. Run tests to verify setup
make test
```

## 📋 Development Guidelines

### Code Style

We use **ruff** for linting and **black** for formatting:

```bash
# Format code
make format

# Check linting
make lint

# Type checking
make type-check
```

### Commit Messages

Follow conventional commits:

```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`

Examples:
- `feat(agents): add new georeferencing agent`
- `fix(bridge): handle connection timeout gracefully`
- `docs(readme): add Docker installation instructions`

### Branching Strategy

- `main` - Stable releases only
- `develop` - Integration branch for features
- `feature/*` - Feature branches
- `fix/*` - Bug fix branches
- `release/*` - Release preparation branches

### Pull Request Process

1. **Create a branch** from `develop` for your change
2. **Write tests** for new functionality
3. **Ensure all tests pass**: `make test`
4. **Run quality checks**: `make lint && make type-check`
5. **Update documentation** if needed
6. **Submit PR** against `develop` branch
6. **Address review comments** promptly

### Testing Requirements

- **Unit tests** for all new functions/classes
- **Integration tests** for QGIS-dependent features
- **Coverage target**: >80% for new code
- Run tests: `make test` or `make test-coverage`

### Code Organization

```
Universal-AI-GIS-Studio/
├── agents/          # Agent system (29 built-in + custom)
├── bridge/          # QGIS Bridge (FastAPI + WebSocket)
├── clusters/        # 25 GIS clusters (M01-M25)
├── core/            # Foundation services
├── database/        # SQLite + migrations + repositories
├── engines/         # Execution engines
├── integrations/    # External AI/MCP integrations
├── mcp_server/      # MCP server (stdio + HTTP)
├── monitoring/      # Audit, health, metrics
├── plugin/          # QGIS 4.x plugin
├── security/        # Auth, permissions, rate limiting
├── skills/          # Skill system
├── workflows/       # DAG workflow engine
└── tests/           # Unit + integration tests
```

### Adding New Features

#### New Cluster (GIS Operation)
1. Create `clusters/mXX_name/` with `handler.py` and `__init__.py`
2. Implement `execute()` method in handler
3. Register in `clusters/registry.py`
4. Add capability registration
5. Write tests in `tests/unit/test_clusters.py`

#### New Agent
1. Add agent class in `agents/builtins/agent_name.py`
2. Register in `agents/builtins/__init__.py`
3. Add tool allowlist in `agents/agent_manager.py`
4. Register capabilities

#### New Engine
1. Create `engines/engine_name/` with implementation
2. Add to `engines/__init__.py`
3. Register capabilities
4. Add emergency stop integration

#### New MCP Tool
1. Add tool definition in `mcp_server/registry.py`
2. Implement handler in `mcp_server/tools/`
3. Add to `bridge/dispatcher.py` if bridge-side
4. Register in capability registry

### Security Considerations

- **Never commit secrets** - Use `.env` files
- **Validate all inputs** - Use Pydantic models
- **Principle of least privilege** - Agent tool allowlists
- **Audit logging** - All security events
- **Rate limiting** - Protect against abuse

## 📚 Documentation Standards

- **Docstrings** for all public classes/functions (Google style)
- **Type hints** for all function signatures
- **README updates** for new features
- **Architecture docs** in `docs/` for major changes
- **Inline comments** for complex logic

## 🏷️ Release Process

1. Update `CHANGELOG.md`
2. Bump version in `pyproject.toml`
3. Create release branch: `release/vX.Y.Z`
4. Run full test suite: `make test`
5. Build: `make build`
6. Create GitHub Release with artifacts
7. Publish to PyPI: `twine upload dist/*`
8. Merge to `main` and tag

## 📞 Getting Help

- **Discord/Slack**: [Link if available]
- **GitHub Discussions**: For questions and ideas
- **GitHub Issues**: For bugs and feature requests
- **Email**: maintainers@universal-ai-gis.org

## 📜 Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold this code.

### Our Standards

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Respect differing opinions and experiences

## 🙏 Recognition

Contributors are recognized in:
- `CONTRIBUTORS.md` file
- Release notes
- GitHub contributors graph

---

**Thank you for contributing to Universal AI GIS Studio!** 🎉

Your contributions make AI-powered GIS automation accessible to everyone.