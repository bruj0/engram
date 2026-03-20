#!/usr/bin/env python3
"""Engram — preCompact hook for Cursor.

Fires BEFORE Cursor compresses the context window. This is the right moment to:
1. Ensure the session record exists (resilient to restarts).
2. Inject instructions telling the agent to call mem_session_summary with
   the content it's about to compact, so nothing is lost.
3. Inject prior session context so the compaction summary is well-informed.

Output: JSON {"additional_context": "..."} — Cursor injects this into the
compaction prompt before summarization runs.

Note: This is different from Claude Code's post-compaction hook (which fires
AFTER compaction). Firing before gives the agent a chance to persist the
full context before it's compressed.
"""

import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _helpers import (
    detect_project,
    engram_get,
    engram_post,
    ensure_server_running,
    get_workspace_root,
    read_hook_input,
)

COMPACTION_PROTOCOL = """\
## Engram Persistent Memory — ACTIVE PROTOCOL

You have engram memory tools (mem_save, mem_search, mem_context, mem_session_summary).
This protocol is MANDATORY and ALWAYS ACTIVE.

### PROACTIVE SAVE — do NOT wait for user to ask
Call `mem_save` IMMEDIATELY after ANY of these:
- Decision made (architecture, convention, workflow, tool choice)
- Bug fixed (include root cause)
- Convention or workflow documented/updated
- Non-obvious discovery, gotcha, or edge case found
- Pattern established (naming, structure, approach)
- User preference or constraint learned
- Feature implemented with non-obvious approach

**Self-check after EVERY task**: "Did I just make a decision, fix a bug, learn something, or establish a convention? If yes → mem_save NOW."

### SEARCH MEMORY when:
- User asks to recall anything ("remember", "what did we do", "acordate", "qué hicimos")
- Starting work on something that might have been done before
- User mentions a topic you have no context on

### SESSION CLOSE — before saying "done"/"listo":
Call `mem_session_summary` with: Goal, Discoveries, Accomplished, Next Steps, Relevant Files.

---

CRITICAL — COMPACTION IS ABOUT TO HAPPEN. Follow these steps IN ORDER before the summary is written:

1. FIRST: Call `mem_session_summary` with a full summary of what has been accomplished in this session so far.
   Use the Goal / Discoveries / Accomplished / Next Steps / Relevant Files structure.
   This preserves everything done before the context window is compressed.

2. THEN: When writing the compaction summary, include this instruction for the next agent instance:
   "AFTER COMPACTION: Call mem_context to recover session history before continuing."

All steps are MANDATORY. Without step 1, everything done in this session is lost.\
"""


def main() -> None:
    hook_input = read_hook_input()
    conversation_id = hook_input.get("conversation_id", "")
    cwd = get_workspace_root(hook_input)
    project = detect_project(cwd)

    ensure_server_running()

    # Ensure session record exists (resilient to server restarts)
    if conversation_id and project:
        engram_post("/sessions", {"id": conversation_id, "project": project, "directory": cwd})

    # Fetch prior context to make the compaction summary richer
    context = ""
    encoded_project = urllib.parse.quote(project, safe="")
    result = engram_get(f"/context?project={encoded_project}")
    if result:
        context = result.get("context", "")

    additional_context = COMPACTION_PROTOCOL
    if context:
        additional_context += f"\n\n{context}"

    print(json.dumps({"additional_context": additional_context}))


if __name__ == "__main__":
    main()
