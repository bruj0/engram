#!/usr/bin/env python3
"""Engram — stop hook for Cursor (runs async after agent loop ends).

Marks the session as ended via the HTTP API so engram can close the session
record and update its end timestamp.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _helpers import engram_post, ensure_server_running, read_hook_input


def main() -> None:
    hook_input = read_hook_input()
    conversation_id = hook_input.get("conversation_id", "")

    if not conversation_id:
        return

    ensure_server_running()
    engram_post(f"/sessions/{conversation_id}/end", {})


if __name__ == "__main__":
    main()
