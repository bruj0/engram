"""Engram — shared helpers for Cursor hooks.

All functions use stdlib only (no pip deps). Designed to be imported by the
individual hook scripts via sys.path manipulation, since they live in the same
directory.

Failure contract: every public function is silent on error — hooks must never
crash Cursor's agent loop. Use the `_try` wrapper internally.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


# ─── Configuration ───────────────────────────────────────────────────────────

def get_engram_url() -> str:
    port = os.environ.get("ENGRAM_PORT", "7437")
    return f"http://127.0.0.1:{port}"


# ─── Project detection ───────────────────────────────────────────────────────

def detect_project(directory: str) -> str:
    """Infer project name from git remote, then git root, then basename.

    Priority: git remote origin repo name → git root basename → cwd basename.
    Mirrors the logic in the Claude Code _helpers.sh.
    """
    if not directory:
        return os.path.basename(os.getcwd())

    # Try git remote origin URL
    try:
        url = subprocess.check_output(
            ["git", "-C", directory, "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if url:
            # Handles SSH (git@github.com:user/repo.git) and HTTPS URLs
            name = url.rstrip("/").rstrip(".git").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
            name = name.removesuffix(".git")
            if name:
                return name
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback: git root directory name (works inside worktrees)
    try:
        root = subprocess.check_output(
            ["git", "-C", directory, "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if root:
            return os.path.basename(root)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return os.path.basename(directory)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def engram_get(path: str, timeout: float = 3.0) -> dict[str, Any] | None:
    """GET from the engram HTTP API. Returns parsed JSON or None on any error."""
    url = get_engram_url() + path
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def engram_post(path: str, payload: dict[str, Any], timeout: float = 3.0) -> None:
    """POST to the engram HTTP API. Fire-and-forget — errors are silently ignored."""
    url = get_engram_url() + path
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=timeout).close()
    except Exception:
        pass


# ─── Server lifecycle ─────────────────────────────────────────────────────────

def ensure_server_running() -> None:
    """Start the engram server if the health endpoint is not reachable.

    Uses a single 0.5 s settle delay after spawning — acceptable for
    sessionStart which is not latency-critical.
    """
    url = get_engram_url()
    try:
        urllib.request.urlopen(url + "/health", timeout=1).close()
        return  # Already running
    except Exception:
        pass

    engram_bin = os.environ.get("ENGRAM_BIN", "engram")
    try:
        subprocess.Popen(
            [engram_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(0.5)
    except FileNotFoundError:
        pass  # engram binary not on PATH — nothing we can do


# ─── stdin parsing ────────────────────────────────────────────────────────────

def read_hook_input() -> dict[str, Any]:
    """Read and parse the JSON payload Cursor sends on stdin.

    Returns an empty dict if stdin is empty or not valid JSON — hooks
    should degrade gracefully rather than crash.
    """
    try:
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)
    except Exception:
        pass
    return {}


def get_workspace_root(hook_input: dict[str, Any]) -> str:
    """Extract the workspace root from hook input, with env var fallback."""
    roots = hook_input.get("workspace_roots", [])
    if roots:
        return roots[0]
    return os.environ.get("CURSOR_PROJECT_DIR", os.getcwd())
