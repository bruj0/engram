[← Back to README](../README.md)

# Plugins

- [OpenCode Plugin](#opencode-plugin)
- [Claude Code Plugin](#claude-code-plugin)
- [Cursor Plugin](#cursor-plugin)
- [Privacy](#privacy)

---

## OpenCode Plugin

For [OpenCode](https://opencode.ai) users, a thin TypeScript plugin adds enhanced session management on top of the MCP tools:

```bash
# Install via engram (recommended — works from Homebrew or binary install)
engram setup opencode

# Or manually: cp plugin/opencode/engram.ts ~/.config/opencode/plugins/
```

The plugin auto-starts the HTTP server if it's not already running — no manual `engram serve` needed.

> **Local model compatibility:** The plugin works with all models, including local ones served via llama.cpp, Ollama, or similar. The Memory Protocol is concatenated into the existing system prompt (not added as a separate system message), so models with strict Jinja templates (Qwen, Mistral/Ministral) work correctly.

### What the Plugin Does

The plugin:
- **Auto-starts** the engram server if not running
- **Auto-imports** git-synced memories from `.engram/manifest.json` if present in the project
- **Creates sessions** on-demand via `ensureSession()` (resilient to restarts/reconnects)
- **Injects the Memory Protocol** into the agent's system prompt via `chat.system.transform` — strict rules for when to save, when to search, and a mandatory session close protocol. The protocol is concatenated into the existing system message (not pushed as a separate one), ensuring compatibility with models that only accept a single system block (Qwen, Mistral/Ministral via llama.cpp, etc.)
- **Injects previous session context** into the compaction prompt
- **Instructs the compressor** to tell the new agent to persist the compacted summary via `mem_session_summary`
- **Strips `<private>` tags** before sending data

**No raw tool call recording** — the agent handles all memory via `mem_save` and `mem_session_summary`.

### Memory Protocol (injected via system prompt)

The plugin injects a strict protocol into every agent message:

- **WHEN TO SAVE**: Mandatory after bugfixes, decisions, discoveries, config changes, patterns, preferences
- **WHEN TO SEARCH**: Reactive (user says "remember"/"recordar") + proactive (starting work that might overlap past sessions)
- **SESSION CLOSE**: Mandatory `mem_session_summary` before ending — "This is NOT optional. If you skip this, the next session starts blind."
- **AFTER COMPACTION**: Immediately call `mem_context` to recover state

### Three Layers of Memory Resilience

The OpenCode plugin uses a defense-in-depth strategy to ensure memories survive compaction:

| Layer | Mechanism | Survives Compaction? |
|-------|-----------|---------------------|
| **System Prompt** | `MEMORY_INSTRUCTIONS` concatenated into existing system prompt via `chat.system.transform` | Always present |
| **Compaction Hook** | Auto-saves checkpoint + injects context + reminds compressor | Fires during compaction |
| **Agent Config** | "After compaction, call `mem_context`" in agent prompt | Always present |

---

## Claude Code Plugin

For [Claude Code](https://docs.anthropic.com/en/docs/claude-code) users, a plugin adds enhanced session management using Claude's native hook and skill system:

```bash
# Install via Claude Code marketplace (recommended)
claude plugin marketplace add Gentleman-Programming/engram
claude plugin install engram

# Or via engram binary (works from Homebrew or binary install)
engram setup claude-code

# Or for local development/testing from the repo
claude --plugin-dir ./plugin/claude-code
```

### What the Plugin Provides (vs bare MCP)

| Feature | Bare MCP | Plugin |
|---------|----------|--------|
| 13 memory tools | ✓ | ✓ |
| Session tracking (auto-start) | ✗ | ✓ |
| Auto-import git-synced memories | ✗ | ✓ |
| Compaction recovery | ✗ | ✓ |
| Memory Protocol skill | ✗ | ✓ |
| Previous session context injection | ✗ | ✓ |

### Plugin Structure

```
plugin/claude-code/
├── .claude-plugin/plugin.json     # Plugin manifest
├── .mcp.json                      # Registers engram MCP server
├── hooks/hooks.json               # SessionStart + SubagentStop + Stop lifecycle hooks
├── scripts/
│   ├── session-start.sh           # Ensures server, creates session, imports chunks, injects context
│   ├── post-compaction.sh         # Injects previous context + recovery instructions
│   ├── subagent-stop.sh           # Passive capture trigger on subagent completion
│   └── session-stop.sh            # Logs end-of-session event
└── skills/memory/SKILL.md         # Memory Protocol (when to save, search, close, recover)
```

### How It Works

**On session start** (`startup`):
1. Ensures the engram HTTP server is running
2. Creates a new session via the API
3. Auto-imports git-synced chunks from `.engram/manifest.json` (if present)
4. Injects previous session context into Claude's initial context

**On compaction** (`compact`):
1. Injects the previous session context + compacted summary
2. Tells the agent: "FIRST ACTION REQUIRED — call `mem_session_summary` with this content before doing anything else"
3. This ensures no work is lost when context is compressed

**Memory Protocol skill** (always available):
- Strict rules for **when to save** (mandatory after bugfixes, decisions, discoveries)
- **When to search** memory (reactive + proactive)
- **Session close protocol** — mandatory `mem_session_summary` before ending
- **After compaction** — 3-step recovery: persist summary → load context → continue

---

## Cursor Plugin

For [Cursor](https://cursor.com) users, a set of Python hooks adds session tracking, compaction recovery, and the Memory Protocol on top of the MCP tools:

```bash
# Install via engram binary
engram setup cursor
```

This copies five Python scripts to `~/.cursor/hooks/engram/`, merges lifecycle hook entries into `~/.cursor/hooks.json`, and registers the MCP server in `~/.cursor/mcp.json`. Python 3.6+ is required; no third-party packages are needed.

### What the Plugin Provides (vs bare MCP)

| Feature | Bare MCP | Plugin |
|---------|----------|--------|
| 13 memory tools | ✓ | ✓ |
| Session tracking (auto-start) | ✗ | ✓ |
| Auto-import git-synced memories | ✗ | ✓ |
| Compaction recovery (pre-compact) | ✗ | ✓ |
| Memory Protocol context injection | ✗ | ✓ |
| Passive capture from subagents | ✗ | ✓ |

### Plugin Structure

```
plugin/cursor/
├── .cursor/
│   ├── hooks.json              # Cursor hook config (camelCase events, absolute script paths)
│   └── mcp.json                # Cursor MCP registration
└── scripts/
    ├── _helpers.py             # detect_project(), HTTP helpers, server lifecycle (stdlib only)
    ├── session_start.py        # sessionStart — injects Memory Protocol + prior context
    ├── session_stop.py         # stop — marks session ended
    ├── subagent_stop.py        # subagentStop — passive capture from Task subagents
    └── post_compaction.py      # preCompact — instructs agent to persist before compaction
```

### How It Works

**On session start** (`sessionStart`):
1. Ensures the engram HTTP server is running (starts it if not)
2. Migrates the project name if the git remote differs from the directory basename
3. Creates a new session via the API
4. Auto-imports git-synced chunks from `.engram/manifest.json` (if present)
5. Injects the Memory Protocol + prior session context as `additional_context`

**Before compaction** (`preCompact`):
1. Ensures the session record exists (resilient to server restarts)
2. Fetches prior session context to inform the compaction summary
3. Instructs the agent to call `mem_session_summary` before the context is compressed
4. This is fired **before** compaction (unlike Claude Code which fires after), giving the agent a chance to save context first

**On subagent stop** (`subagentStop`):
- POSTs the subagent output to `/observations/passive` for automatic extraction
- Defensive: checks multiple candidate field names (`output`, `stdout`, `result`, `content`)

**On session stop** (`stop`):
- POSTs to `/sessions/{id}/end` to close the session record

### Cursor vs Claude Code Hook Differences

| Aspect | Claude Code | Cursor |
|--------|-------------|--------|
| Event names | `SessionStart`, `Stop` | `sessionStart`, `stop` |
| Session field | `session_id` | `conversation_id` |
| Working dir field | `cwd` | `workspace_roots[0]` |
| Session start output | Raw text to stdout | JSON `{"additional_context": "..."}` |
| Compaction hook | Fires **after** compaction | `preCompact` fires **before** |
| Script format | Bash + jq | Python 3 (stdlib only) |
| Plugin marketplace | Yes | No — install via `engram setup cursor` |

---

## Privacy

Wrap sensitive content in `<private>` tags — it gets stripped at TWO levels:

```
Set up API with <private>sk-abc123</private> key
→ Set up API with [REDACTED] key
```

1. **Plugin layer** — stripped before data leaves the process
2. **Store layer** — `stripPrivateTags()` in Go before any DB write
