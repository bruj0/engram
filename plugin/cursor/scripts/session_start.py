#!/usr/bin/env python3
"""Engram — sessionStart hook for Cursor.

Actions:
1. Ensures the engram server is running.
2. Migrates the project name if it changed (directory basename → git-derived name).
3. Creates a session in engram.
4. Auto-imports git-synced chunks if .engram/manifest.json exists.
5. Injects the Memory Protocol + prior session context as additional_context.

Output: JSON {"additional_context": "..."} — Cursor injects this into the
agent's initial context for the session. No ToolSearch needed; Cursor MCP
tools are always registered (unlike Claude Code's deferred tool system).
"""

import json
import os
import subprocess
import sys
import urllib.parse

# Allow importing _helpers from the same directory regardless of invocation path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _helpers import (
    detect_project,
    engram_get,
    engram_post,
    ensure_server_running,
    get_workspace_root,
    read_hook_input,
)

MEMORY_PROTOCOL = """\
## Engram Persistent Memory — ACTIVE PROTOCOL

You have engram memory tools (mem_save, mem_search, mem_context, mem_session_summary).
This protocol is MANDATORY and ALWAYS ACTIVE.

### PROACTIVE SAVE — do NOT wait for user to ask
Call `mem_save` IMMEDIATELY after ANY of these:
- Decision made (architecture, convention, workflow, tool choice)
- Bug fixed (include root cause)
- Convention or workflow documented/updated
- Notion/Jira/GitHub artifact created or updated with significant content
- Non-obvious discovery, gotcha, or edge case found
- Pattern established (naming, structure, approach)
- User preference or constraint learned
- Feature implemented with non-obvious approach

**Self-check after EVERY task**: "Did I just make a decision, fix a bug, learn something, or establish a convention? If yes → mem_save NOW."

### SEARCH MEMORY when:
- User asks to recall anything ("remember", "what did we do", "acordate", "qué hicimos")
- Starting work on something that might have been done before
- User mentions a topic you have no context on
- User's FIRST message references the project, a feature, or a problem — call `mem_search` with keywords from their message to check for prior work before responding

### SESSION CLOSE — before saying "done"/"listo":
Call `mem_session_summary` with: Goal, Discoveries, Accomplished, Next Steps, Relevant Files.\
"""


def main() -> None:
    hook_input = read_hook_input()
    conversation_id = hook_input.get("conversation_id", "")
    cwd = get_workspace_root(hook_input)
    old_project = os.path.basename(cwd)
    project = detect_project(cwd)

    ensure_server_running()

    # Migrate project name if git remote yields a different name than the dirname
    if old_project and project and old_project != project:
        engram_post("/projects/migrate", {"old_project": old_project, "new_project": project})

    # Create (or re-use) a session for this conversation
    if conversation_id and project:
        engram_post("/sessions", {"id": conversation_id, "project": project, "directory": cwd})

    # Auto-import git-synced chunks when a manifest is present
    manifest = os.path.join(cwd, ".engram", "manifest.json")
    if os.path.isfile(manifest):
        engram_bin = os.environ.get("ENGRAM_BIN", "engram")
        try:
            subprocess.run(
                [engram_bin, "sync", "--import"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Fetch prior session context
    context = ""
    encoded_project = urllib.parse.quote(project, safe="")
    result = engram_get(f"/context?project={encoded_project}")
    if result:
        context = result.get("context", "")

    additional_context = MEMORY_PROTOCOL
    if context:
        additional_context += f"\n\n{context}"

    print(json.dumps({"additional_context": additional_context}))


if __name__ == "__main__":
    main()
