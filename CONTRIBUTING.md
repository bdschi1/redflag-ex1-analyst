# Contributing

## Development Setup

```bash
git clone https://github.com/bdschi1/redflag_ex1_analyst.git
cd redflag_ex1_analyst
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

For the Streamlit dashboard:

```bash
pip install -e ".[dashboard]"
```

## Code Style

- Lint with `ruff check .`
- Format with `ruff format .`
- Type hints encouraged
- Target Python 3.9+

## Testing

```bash
pytest tests/ -v
```

All 157 tests are deterministic -- no API keys or network access needed. Test fixtures dynamically generate PDF and DOCX files via fpdf2 and python-docx.

## Pull Requests

1. Create a feature branch from `main`
2. Make focused, single-purpose commits
3. Ensure all tests pass and `ruff check .` is clean before submitting
4. Open a PR with a clear description of changes
