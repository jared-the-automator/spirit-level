#!/usr/bin/env python3
"""PreToolUse guard — spirit-level.

G1  destructive git over uncommitted work   (Bash)
G2  AI attribution in commit messages       (Bash)
G3  plaintext secrets to non-secret paths   (Write / Edit / Bash)
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

# `git -C /abs/path reset --hard` is the same command with a path in the
# middle, so the flag run has to admit slashes.
#
# Scope: this guard is specifically "destructive to UNCOMMITTED work". Things
# that destroy committed history instead (`push --force`, `branch -D`,
# `worktree remove -f`) are deliberately absent — gating them on whether the
# tree happens to be dirty would fire arbitrarily. They belong to a separate
# guard, not this one.
DESTRUCTIVE_GIT = re.compile(
    r"git\s+(?:[-\w=./ ]+\s+)?"
    r"(reset\s+--hard|checkout\s+(?:--\s|-f\b)|restore\s(?!.*--staged)"
    r"|clean\s+-\w*f|stash\s+(?:drop|clear))"
)
# Quoted text is data, not an instruction. Without stripping it, a commit
# message that merely mentions a destructive command trips the guard.
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"", re.S)
GIT_COMMIT = re.compile(r"git\s+(?:[-\w=./ ]+\s+)?commit\b")
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
# Applied to a single extracted path, never to a whole command line. Matching
# the command would let any stray mention of "credentials" (a comment, an
# unrelated second clause) whitelist the real write target.
#
# Every alternative is anchored to a path component. An unanchored substring
# match would treat `public/credentials.js` and `my-credentials-backup.txt` as
# secrets paths, which is how a key ends up in a web-served directory.
# A secrets file carries data, not code. `credentials.json` is a real secrets
# path; `credentials.js` is source, and treating it as safe puts a key in a
# web-served directory.
_DATA_EXT = r"(?:\.(?:json|ya?ml|ini|conf|cfg|txt|enc|properties|toml))?"
SAFE_TARGET = re.compile(
    r"(?:^|/)\.env(?:\.[\w-]+)?$"
    r"|(?:^|/)\.?credentials?" + _DATA_EXT + r"$"
    r"|(?:^|/)\.?secrets?" + _DATA_EXT + r"$"
    r"|\.pem$|\.key$",
    re.I,
)
# Pseudo-devices are not storage. `curl -H "Authorization: Bearer sk-..."
# 2>/dev/null` must not read as writing a key to disk.
DEV_SINK = re.compile(r"^/dev/(null|stdout|stderr|fd/\d+|tty)$", re.I)

# --- shell write detection -------------------------------------------------
# Redirect forms that actually write: `>`, `>>`, `1>`, `2>`, `&>`, `&>>`, `>|`.
# Excluded: `=>` and `->` (arrows, via the lookbehind) and `>&1` / `>&2` (fd
# duplication, via the `(?!&)`), so that merely PRINTING a secret is allowed.
# An earlier version excluded any digit before `>`, which silently un-guarded
# `1>` — the plain redirect with an explicit fd.
REDIRECT = re.compile(
    r"""(?<![-=<>])(?:\d+|&)?>>?\|?\s*(?!&)['"]?([^\s;|&<>'"]+)""")
TEE = re.compile(r"\btee\b((?:\s+-\w+)*)\s+([^\s;|&<>]+)")
SED_INPLACE = re.compile(r"\bsed\b[^;|&]*?\s-i[\w.]*\s[^;|&]*?([^\s;|&]+)\s*(?:$|[;|&])")
DD_OF = re.compile(r"\bdd\b[^;|&]*?\bof=([^\s;|&]+)")
# Write primitives whose destination this parser cannot reliably extract.
# A credential plus one of these fails CLOSED — better a needless confirm than
# a key on disk.
OPAQUE_WRITE = re.compile(
    r"\bsponge\b|\bperl\b[^;|&]*-\w*i|\bpython[0-9.]*\b[^;|&]*\bopen\s*\("
    r"|\bnode\b[^;|&]*\bwriteFile|\binstall\s+-m|\btruncate\b"
)
HEREDOC = re.compile(r"<<-?\s*['\"]?[A-Za-z_]")
COMMENT = re.compile(r"#[^\n]*$", re.M)
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
    return bool(_git(cwd, "status", "--porcelain"))


def shell_write_targets(command):
    """(writes_to_disk, [targets], all_targets_known).

    Comments are stripped first: a trailing `# see secrets.md` must not
    whitelist the real destination.
    """
    cmd = COMMENT.sub("", command)
    targets = [m.group(1) for m in REDIRECT.finditer(cmd)]
    targets += [m.group(2) for m in TEE.finditer(cmd)]
    targets += [m.group(1) for m in SED_INPLACE.finditer(cmd)]
    targets += [m.group(1) for m in DD_OF.finditer(cmd)]
    targets = [t for t in targets if not DEV_SINK.match(t)]
    opaque = bool(OPAQUE_WRITE.search(cmd)) or bool(HEREDOC.search(cmd))
    writes = bool(targets) or opaque
    return writes, targets, not opaque


def check_bash(payload, command, cfg):
    if re.match(r"\s*GUARD_OK=1\s", command):
        log_event(payload, "bypass", "GUARD_OK", command)
        return  # human-authorized, logged, allowed

    guards = cfg.get("guards", {})

    # Quoted text is data. `git commit -m "reverted the git clean -fd"` is a
    # commit, not a destructive operation.
    unquoted = QUOTED.sub("''", command)

    if (guards.get("destructive_git_over_wip")
            and DESTRUCTIVE_GIT.search(unquoted)
            and wip_present(payload.get("cwd"))):
        deny(payload, "G1",
             "Destructive git over uncommitted work. Commit or stash first; "
             "a human can override with a GUARD_OK=1 prefix.", command)

    if (guards.get("ai_attribution_in_commits")
            and GIT_COMMIT.search(command) and ATTRIBUTION.search(command)):
        deny(payload, "G2",
             "Commit message contains AI attribution. Strip the "
             "Co-Authored-By / Generated-with lines and retry.", command)

    if guards.get("plaintext_secrets") and SECRET_PATTERNS.search(command):
        writes, targets, known = shell_write_targets(command)
        if writes and not (known and targets
                           and all(SAFE_TARGET.search(t) for t in targets)):
            where = ", ".join(targets) if targets else "an undetermined path"
            deny(payload, "G3",
                 f"Credential-shaped string being written to disk ({where}) "
                 "by a shell command. Secrets belong in .env* / credentials "
                 "files.", command)

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
    if SECRET_PATTERNS.search(content) and not SAFE_TARGET.search(path):
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
