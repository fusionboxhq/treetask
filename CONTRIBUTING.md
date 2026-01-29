# Contributing to TreeTask

Thank you for your interest in contributing to TreeTask!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/fusionboxhq/treetask.git
   cd treetask
   ```

2. Create a virtual environment (Python 3.10+ required):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install in development mode with dev dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Running Tests

Run the full test suite:
```bash
pytest
```

Run with coverage report:
```bash
pytest --cov=treetask --cov-report=term-missing
```

Run a specific test file:
```bash
pytest tests/test_executor.py
```

Run a specific test:
```bash
pytest tests/test_executor.py::TestAsyncExecutor::test_simple_tree
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Keep functions focused and single-purpose
- Write docstrings for public APIs

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear, atomic commits
3. Add or update tests for your changes
4. Ensure all tests pass and coverage remains at 100%
5. Update documentation if adding new features
6. Submit a PR with a clear description of the changes

## Reporting Issues

When reporting bugs, please include:
- Python version
- TreeTask version
- Minimal code example that reproduces the issue
- Full error traceback

## Feature Requests

Feature requests are welcome! Please describe:
- The use case you're trying to solve
- How you envision the API working
- Any alternatives you've considered
