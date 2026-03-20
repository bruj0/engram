#!/usr/bin/env python3
"""Engram — subagentStop hook for Cursor (runs async after a Task subagent finishes).

POSTs the subagent's output to the passive capture endpoint. All extraction
logic (pattern matching, dedup, storage) lives in the Go server — this script
is intentionally thin.

Cursor may include the subagent output under different field names depending on
the version. We check the most likely candidates defensively.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _helpers import (
    detect_project,
    engram_post,
    ensure_server_running,
    get_workspace_root,
    read_hook_input,
)

# Candidate field names Cursor might use for subagent output text.
# Listed in priority order — first non-empty value wins.
_OUTPUT_FIELDS = ("output", "stdout", "result", "content")


def main() -> None:
    hook_input = read_hook_input()
    conversation_id = hook_input.get("conversation_id", "")
    cwd = get_workspace_root(hook_input)
    project = detect_project(cwd)

    # Extract subagent output — be defensive about field name
    output = ""
    for field in _OUTPUT_FIELDS:
        value = hook_input.get(field, "")
        if value and isinstance(value, str):
            output = value
            break

    if not output:
        return

    ensure_server_running()
    engram_post(
        "/observations/passive",
        {
            "session_id": conversation_id,
            "content": output,
            "project": project,
            "source": "subagent-stop",
        },
    )


if __name__ == "__main__":
    main()
