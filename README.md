# quant-mm-agent

Agent-augmented market-making bot for decentralized perpetuals exchanges. Primary venue: Hyperliquid.

## Layout

```
CLAUDE.md         Master context. Read this first. Has the next-steps task list.
README.md         You are here.
SETUP.md          One-time environment setup (Python 3.11 + deps).
pyproject.toml    Project metadata and dependencies.
.python-version   Pinned to 3.11.
.env.example      Template for secrets/config. Copy to .env (gitignored).

research/         One markdown file per topic. Research is complete for v1 scoping.
code/             Python: strategies, backtester, connectors, agent layer.
                  Currently has data_recorder/README.md (spec for first coding task).
references/       Saved papers, screenshots, addresses-to-watch, with sources.
prompts/          System prompts and tool specs for the LLM agent layer.
```

## Workflow

1. **Claude.ai chat** — exploration, research, drafting. Output gets saved into this folder.
2. **Claude Code** (in this folder) — implementation, refactoring, running code. Reads `CLAUDE.md` on startup.

Continuity lives in `CLAUDE.md`. If a session produced something, the Session Log gets a line.

## Status

**Research phase complete. Ready to start coding.**

Next session: open this folder in Claude Code. It will read `CLAUDE.md` and find the "Next Steps for Claude Code" section, which has an explicit ordered task list starting with environment setup and the data recorder.

No live capital. No code yet.
