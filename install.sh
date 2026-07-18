#!/usr/bin/env bash
# spirit-level installer. Copies hooks + default config, prints the
# settings.json block to paste. Never edits settings.json for you.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${SPIRIT_LEVEL_DIR:-$HOME/.claude/spirit-level}"
HOOKS="$TARGET/hooks"

echo "==> Installing spirit-level to $TARGET"

if ! command -v python3 >/dev/null 2>&1; then
    echo "    ERROR: python3 not found. spirit-level needs Python 3.8+." >&2
    exit 1
fi

mkdir -p "$HOOKS" "$TARGET/state"

# Preserve an existing house-rules.md; it holds the user's own content.
for f in protocol_lib.py guard.py protocol-inject.py protocol-stop.py protocol-edit-audit.py; do
    cp "$REPO_DIR/hooks/$f" "$HOOKS/$f"
done
chmod +x "$HOOKS"/*.py

if [ -f "$HOOKS/house-rules.md" ]; then
    echo "    - house-rules.md already exists, left untouched"
else
    cp "$REPO_DIR/hooks/house-rules.md" "$HOOKS/house-rules.md"
    echo "    - house-rules.md created (empty; add your always-on rules)"
fi

if [ -f "$TARGET/config.json" ]; then
    echo "    - config.json already exists, left untouched"
else
    cp "$REPO_DIR/config.example.json" "$TARGET/config.json"
    echo "    - config.json created from defaults"
fi

echo "    - hooks installed"

# Optional: the verification-gate skill
SKILLS="$HOME/.claude/skills"
if [ -d "$SKILLS" ]; then
    read -r -p "==> Install the verification-gate skill to $SKILLS? [y/N] " ans
    if [[ "${ans:-n}" =~ ^[Yy]$ ]]; then
        mkdir -p "$SKILLS/verification-gate"
        cp "$REPO_DIR/skills/verification-gate/SKILL.md" "$SKILLS/verification-gate/"
        echo "    - verification-gate skill installed"
    fi
fi

cat <<EOF

==> Done. Add this to the "hooks" object in ~/.claude/settings.json:

{
  "hooks": {
    "UserPromptSubmit": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "python3 $HOOKS/protocol-inject.py" } ] }
    ],
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [
        { "type": "command", "command": "python3 $HOOKS/guard.py" } ] },
      { "matcher": "Edit|Write", "hooks": [
        { "type": "command", "command": "python3 $HOOKS/guard.py" } ] }
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write", "hooks": [
        { "type": "command", "command": "python3 $HOOKS/protocol-edit-audit.py" } ] }
    ],
    "Stop": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "python3 $HOOKS/protocol-stop.py" } ] }
    ]
  }
}

If you already have hooks configured for these events, add these entries to
the existing arrays rather than replacing them. Hooks compose.

Next steps:
  1. Edit $TARGET/config.json — set native_models to the model(s) that
     already behave the way you want.
  2. Put your own always-on rules in $HOOKS/house-rules.md
  3. Start a new session. Verify with:
     tail -1 $TARGET/log.jsonl

EOF
