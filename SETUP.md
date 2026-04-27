# Setup

One-time setup for the project. Done once per machine.

## Prerequisites

- Python 3.11 (pinned in `.python-version`)
- A package manager: `uv` (recommended, fast) or `pip` (fine)
- Git
- Optionally: pyenv (for managing Python versions) if you don't already have 3.11

## Steps

### 1. Get Python 3.11

If you have pyenv:

```bash
pyenv install 3.11
# pyenv will pick up .python-version automatically when you cd in
```

Otherwise install Python 3.11 however you normally do. The `.python-version` file tells pyenv-aware tools which version to use.

### 2. Create a virtual environment

With `uv` (recommended):

```bash
uv venv
source .venv/bin/activate
```

With plain Python:

```bash
python3.11 -m venv .venv
source .venv/bin/activate    # mac/linux
# .venv\Scripts\activate     # windows
```

### 3. Install dependencies

With `uv`:

```bash
uv pip install -e ".[dev]"
```

With plain pip:

```bash
pip install -e ".[dev]"
```

The `-e` (editable) flag means changes to your code don't require reinstalling.

### 4. Configure secrets

```bash
cp .env.example .env
# Open .env in your editor and fill in values.
# At minimum to get started, you need ANTHROPIC_API_KEY.
# Hyperliquid keys can wait until you're actually ready to talk to the venue.
```

`.env` is gitignored. Never commit it.

### 5. Verify the install works

```bash
python -c "import hyperliquid; import anthropic; print('ok')"
```

If that prints `ok`, you're set up.

## What's next

Open `CLAUDE.md` and read the "Next Steps for Claude Code" section at the bottom. That's the explicit task list for the first coding session.
