#!/usr/bin/env python3
"""PreToolUse guard — spirit-level.

G1  destructive git over uncommitted work   (Bash)
G2  AI attribution in commit messages       (Bash)
G3  plaintext secrets to non-secret paths   (Write / Edit)
G4  repo pushed to a forbidden remote       (Bash, opt-in via config)

Applies to every model: guards cost no tokens, and data loss is data loss.
Override: prefix a Bash command with GUARD_OK=1 -> allowed, logged as bypass.
Deny contract: JSON permissionDecision, per the Claude Code hooks docs.
"""
import json
import re
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from protocol_lib import load_config, log_event, read_payload

DESTRUCTIVE_GIT = re.compile(
    r"git\s+(?:[-\w=. ]+\s+)?"
    r"(reset\s+--hard|checkout\s+--\s|restore\s(?!.*--staged)"
    r"|clean\s+-\w*f|stash\s+drop)"
)
ATTRIBUTION = re.compile(
    r"Co-Authored-By:\s*(?:Claude|GPT|Copilot|Cursor|Gemini)"
    r"|Generated with \[?(?:Claude|Cursor|Copilot)"
    r"|\N{ROBOT FACE} Generated",
    re.I,
)
SECRET_PATTERNS = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}"
    r"|github_pat_[A-Za-z0-9_]{22,}|xox[bp]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
SECRET_SAFE_PATH = re.compile(
    r"(^|/)\.env(\.|$)|credentials|secrets?\.|\.pem$|\.key$|\.gitignore$", re.I
)
GIT_REMOTE_TOUCH = re.compile(
    r"git\s(?:.*\s)?(?:push|remote\s+(?:add|set-url))\b")


def deny(payload, rule, reason, detail):
    log_event(payload, "deny", rule, detail)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"[{rule}] {reason}",
        }
    }))
    sys.exit(0)


def _git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd or ".", *args],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def wip_present(cwd):
    # Empty output also means "clean tree"; either way, nothing to protect.
    return bool(_git(cwd, "status", "--porcelain"))


def check_bash(payload, command, cfg):
    if re.match(r"\s*GUARD_OK=1\s", command):
        log_event(payload, "bypass", "GUARD_OK", command)
        return  # human-authorized, logged, allowed

    guards = cfg.get("guards", {})

    if (guards.get("destructive_git_over_wip")
            and DESTRUCTIVE_GIT.search(command)
            and wip_present(payload.get("cwd"))):
        deny(payload, "G1",
             "Destructive git over uncommitted work. Commit or stash first; "
             "a human can override with a GUARD_OK=1 prefix.", command)

    if (guards.get("ai_attribution_in_commits")
            and "git commit" in command and ATTRIBUTION.search(command)):
        deny(payload, "G2",
             "Commit message contains AI attribution. Strip the "
             "Co-Authored-By / Generated-with lines and retry.", command)

    for pin in cfg.get("remote_pins", []):
        forbidden = pin.get("forbid_remote")
        if not forbidden or not GIT_REMOTE_TOUCH.search(command):
            continue
        if forbidden.lower() not in command.lower():
            continue
        exempt = pin.get("exempt_path_contains")
        if exempt and re.search(r"(?:-C\s+|cd\s+)[^;&|]*" + re.escape(exempt),
                                command):
            continue
        if _git(payload.get("cwd"), "rev-parse", "--show-toplevel") != pin.get("repo"):
            continue
        deny(payload, "G4",
             f"This repo must not push to or adopt '{forbidden}' as a remote"
             + (f" ({pin['reason']})" if pin.get("reason") else "") + ".",
             command)


def check_write(payload, tool_input, cfg):
    if not cfg.get("guards", {}).get("plaintext_secrets"):
        return
    path = tool_input.get("file_path") or ""
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    if SECRET_PATTERNS.search(content) and not SECRET_SAFE_PATH.search(path):
        deny(payload, "G3",
             "Credential-shaped string headed for a non-secrets file. "
             "Secrets belong in .env* / credentials paths.", path)


def main():
    payload = read_payload()
    cfg = load_config()
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if tool == "Bash":
        check_bash(payload, tool_input.get("command") or "", cfg)
    elif tool in ("Write", "Edit"):
        check_write(payload, tool_input, cfg)
    # Silence = defer to the normal permission flow.


if __name__ == "__main__":
    main()
