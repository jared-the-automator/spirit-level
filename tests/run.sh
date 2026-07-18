#!/usr/bin/env bash
# spirit-level test suite. Fixture-driven; runs fully isolated in a temp
# SPIRIT_LEVEL_DIR so it never touches your real log, state, or config.
#
#   ./tests/run.sh
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
H="$REPO/hooks"
SCRATCH="$(mktemp -d)"
export SPIRIT_LEVEL_DIR="$SCRATCH/protocol"
mkdir -p "$SPIRIT_LEVEL_DIR"
PASS=0
FAIL=0

cleanup() { rm -rf "$SCRATCH"; }
trap cleanup EXIT

check() { # name, expected substring or '-' for empty, actual
    local name="$1" expect="$2" actual="$3"
    if [ "$expect" = "-" ]; then
        if [ -z "$actual" ]; then
            echo "  PASS  $name"; PASS=$((PASS+1))
        else
            echo "  FAIL  $name — expected no output, got: ${actual:0:110}"; FAIL=$((FAIL+1))
        fi
    elif printf '%s' "$actual" | grep -qF "$expect"; then
        echo "  PASS  $name"; PASS=$((PASS+1))
    else
        echo "  FAIL  $name — wanted '$expect', got: ${actual:0:150}"; FAIL=$((FAIL+1))
    fi
}

write_config() { printf '%s' "$1" > "$SPIRIT_LEVEL_DIR/config.json"; }

# ---------- fixtures ----------
NATIVE_T="$SCRATCH/native.jsonl"
OTHER_T="$SCRATCH/other.jsonl"
printf '{"type":"assistant","message":{"model":"claude-opus-4-8"}}\n{"type":"assistant","message":{"model":"claude-fable-5"}}\n' > "$NATIVE_T"
printf '{"type":"assistant","message":{"model":"claude-fable-5"}}\n{"type":"assistant","message":{"model":"claude-opus-4-8"}}\n' > "$OTHER_T"

CLEAN="$SCRATCH/clean"; DIRTY="$SCRATCH/dirty"
for R in "$CLEAN" "$DIRTY"; do
    git init -q "$R"
    git -C "$R" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
done
echo wip > "$DIRTY/file.txt"

pay() { # session transcript cwd extra_json
    printf '{"session_id":"%s","transcript_path":"%s","cwd":"%s"%s}' "$1" "$2" "$3" "$4"
}
bash_pay() { # session cwd command
    python3 -c "
import json,sys
print(json.dumps({'session_id':sys.argv[1],'transcript_path':sys.argv[2],
 'cwd':sys.argv[3],'tool_name':'Bash','tool_input':{'command':sys.argv[4]}}))" \
    "$1" "$OTHER_T" "$2" "$3"
}
write_pay() { # session tool path content
    python3 -c "
import json,sys
key = 'content' if sys.argv[2]=='Write' else 'new_string'
print(json.dumps({'session_id':sys.argv[1],'transcript_path':sys.argv[5],
 'tool_name':sys.argv[2],'tool_input':{'file_path':sys.argv[3], key:sys.argv[4]}}))" \
    "$1" "$2" "$3" "$4" "$OTHER_T"
}

write_config '{}'

echo "== model gating =="
OUT=$(pay s-nat "$NATIVE_T" "$CLEAN" "" | python3 "$H/protocol-inject.py")
check "native model skips baseline" "-" "$OUT"
OUT=$(pay s-oth "$OTHER_T" "$CLEAN" "" | python3 "$H/protocol-inject.py")
check "non-native gets baseline" "BASELINE" "$OUT"
check "baseline includes rule 1" "Surface the overlooked" "$OUT"
check "baseline includes rule 5" "Assumptions get verified" "$OUT"
OUT=$(pay s-unk "/nonexistent/path" "$CLEAN" "" | python3 "$H/protocol-inject.py")
check "unknown model gets baseline (fail-safe)" "BASELINE" "$OUT"
write_config '{"native_models":[]}'
OUT=$(pay s-none "$NATIVE_T" "$CLEAN" "" | python3 "$H/protocol-inject.py")
check "empty native_models -> everyone gets baseline" "BASELINE" "$OUT"
write_config '{"native_models":["claude-opus"]}'
OUT=$(pay s-cfg "$OTHER_T" "$CLEAN" "" | python3 "$H/protocol-inject.py")
check "config can mark any model native" "-" "$OUT"
write_config '{}'

echo "== house rules =="
cp "$H/house-rules.md" "$SCRATCH/house-rules.backup"
printf 'MY HOUSE RULE: always X\n' > "$H/house-rules.md"
OUT=$(pay s-h1 "$NATIVE_T" "$CLEAN" "" | python3 "$H/protocol-inject.py")
check "house rules inject for native model" "MY HOUSE RULE" "$OUT"
OUT=$(pay s-h2 "$OTHER_T" "$CLEAN" "" | python3 "$H/protocol-inject.py")
check "house rules + baseline for non-native" "MY HOUSE RULE" "$OUT"
check "  ...and baseline still present" "BASELINE" "$OUT"
cp "$SCRATCH/house-rules.backup" "$H/house-rules.md"
OUT=$(pay s-h3 "$NATIVE_T" "$CLEAN" "" | python3 "$H/protocol-inject.py")
check "empty house rules inject nothing" "-" "$OUT"

echo "== G1 destructive git over WIP =="
OUT=$(bash_pay s1 "$DIRTY" "git reset --hard HEAD~1" | python3 "$H/guard.py")
check "denied on dirty tree" '"permissionDecision": "deny"' "$OUT"
check "  ...names G1" "[G1]" "$OUT"
OUT=$(bash_pay s1 "$CLEAN" "git reset --hard HEAD~1" | python3 "$H/guard.py")
check "allowed on clean tree" "-" "$OUT"
OUT=$(bash_pay s1 "$DIRTY" "git checkout -- file.txt" | python3 "$H/guard.py")
check "checkout -- denied on dirty" "[G1]" "$OUT"
OUT=$(bash_pay s1 "$DIRTY" "git restore --staged file.txt" | python3 "$H/guard.py")
check "restore --staged allowed" "-" "$OUT"
OUT=$(bash_pay s1 "$DIRTY" "git status && git log --oneline" | python3 "$H/guard.py")
check "innocent git allowed on dirty" "-" "$OUT"
OUT=$(bash_pay s1 "$DIRTY" "GUARD_OK=1 git reset --hard HEAD~1" | python3 "$H/guard.py")
check "GUARD_OK bypass allowed" "-" "$OUT"
write_config '{"guards":{"destructive_git_over_wip":false}}'
OUT=$(bash_pay s1 "$DIRTY" "git reset --hard HEAD~1" | python3 "$H/guard.py")
check "guard disabled via config" "-" "$OUT"
write_config '{}'

echo "== G2 AI attribution =="
OUT=$(bash_pay s2 "$CLEAN" 'git commit -m "fix: thing

Co-Authored-By: Claude <noreply@anthropic.com>"' | python3 "$H/guard.py")
check "Co-Authored-By denied" "[G2]" "$OUT"
OUT=$(bash_pay s2 "$CLEAN" 'git commit -m "fix: a normal message"' | python3 "$H/guard.py")
check "clean commit allowed" "-" "$OUT"

echo "== G3 plaintext secrets =="
FAKE_KEY="sk-ant-api03-$(printf 'A%.0s' {1..24})"
OUT=$(write_pay s3 Write /tmp/notes.md "key is $FAKE_KEY" | python3 "$H/guard.py")
check "secret to .md denied" "[G3]" "$OUT"
OUT=$(write_pay s3 Write /home/x/.env "KEY=$FAKE_KEY" | python3 "$H/guard.py")
check "secret to .env allowed" "-" "$OUT"
OUT=$(write_pay s3 Edit /tmp/app.js "const t = \"ghp_$(printf 'a%.0s' {1..36})\"" | python3 "$H/guard.py")
check "Edit with token denied" "[G3]" "$OUT"
OUT=$(write_pay s3 Write /tmp/notes.md "the skeleton of the plan" | python3 "$H/guard.py")
check "prose starting with sk- not a false positive" "-" "$OUT"

echo "== G4 remote pinning =="
write_config "{\"remote_pins\":[{\"repo\":\"$CLEAN\",\"forbid_remote\":\"me/other\",\"reason\":\"unrelated histories\",\"exempt_path_contains\":\"nested\"}]}"
OUT=$(bash_pay s4 "$CLEAN" "git push git@github.com:me/other.git main" | python3 "$H/guard.py")
check "forbidden remote denied" "[G4]" "$OUT"
check "  ...includes reason" "unrelated histories" "$OUT"
OUT=$(bash_pay s4 "$CLEAN" "git push origin main" | python3 "$H/guard.py")
check "allowed remote passes" "-" "$OUT"
OUT=$(bash_pay s4 "$CLEAN" "git -C nested/proj push git@github.com:me/other.git main" | python3 "$H/guard.py")
check "nested exempt path allowed" "-" "$OUT"
OUT=$(bash_pay s4 "$DIRTY" "git push git@github.com:me/other.git main" | python3 "$H/guard.py")
check "different repo unaffected" "-" "$OUT"
write_config '{}'

echo "== stop advisories =="
UP="$SCRATCH/upstream.git"; WK="$SCRATCH/work"
git init -q --bare "$UP"
git clone -q "$UP" "$WK" 2>/dev/null
git -C "$WK" -c user.email=t@t -c user.name=t commit -q --allow-empty -m one
BRANCH=$(git -C "$WK" rev-parse --abbrev-ref HEAD)
git -C "$WK" push -q -u origin "$BRANCH" 2>/dev/null
git -C "$WK" -c user.email=t@t -c user.name=t commit -q --allow-empty -m two
OUT=$(pay s-push "$OTHER_T" "$WK" "" | python3 "$H/protocol-stop.py")
check "unpushed advisory fires" "unpushed commit" "$OUT"
check "  ...as a block decision" '"decision": "block"' "$OUT"
OUT=$(pay s-push "$OTHER_T" "$WK" "" | python3 "$H/protocol-stop.py")
check "advisory only once per session" "-" "$OUT"
OUT=$(printf '{"session_id":"s-push2","transcript_path":"%s","cwd":"%s","stop_hook_active":true}' "$OTHER_T" "$WK" | python3 "$H/protocol-stop.py")
check "stop_hook_active exits silently" "-" "$OUT"
OUT=$(pay s-clean "$OTHER_T" "$CLEAN" "" | python3 "$H/protocol-stop.py")
check "no advisory when nothing unpushed" "-" "$OUT"
write_config '{"advisories":{"turn_interval_reminder":2,"turn_reminder_text":"CHECKPOINT"}}'
pay s-turn "$OTHER_T" "$CLEAN" "" | python3 "$H/protocol-stop.py" >/dev/null
OUT=$(pay s-turn "$OTHER_T" "$CLEAN" "" | python3 "$H/protocol-stop.py")
check "turn-interval reminder fires at N" "CHECKPOINT" "$OUT"
write_config '{}'

echo "== repeated-edit audit =="
for _ in 1 2; do
    write_pay s-edit Write /tmp/hot.js "x" | python3 "$H/protocol-edit-audit.py" >/dev/null
done
OUT=$(write_pay s-edit Write /tmp/hot.js "x" | python3 "$H/protocol-edit-audit.py")
check "3rd edit warns" "REPEATED EDIT" "$OUT"
check "  ...via additionalContext" "additionalContext" "$OUT"
write_config '{"advisories":{"repeated_edit_threshold":0}}'
OUT=$(write_pay s-edit2 Write /tmp/hot2.js "x" | python3 "$H/protocol-edit-audit.py")
check "threshold 0 disables" "-" "$OUT"
write_config '{}'

echo "== config robustness =="
printf '{ this is not json' > "$SPIRIT_LEVEL_DIR/config.json"
OUT=$(bash_pay s-bad "$DIRTY" "git reset --hard HEAD~1" | python3 "$H/guard.py" 2>/dev/null)
check "broken config -> guards stay ON" "[G1]" "$OUT"
rm -f "$SPIRIT_LEVEL_DIR/config.json"
OUT=$(bash_pay s-nocfg "$DIRTY" "git reset --hard HEAD~1" | python3 "$H/guard.py")
check "missing config -> defaults apply" "[G1]" "$OUT"
write_config '{}'

echo "== log integrity =="
OUT=$(python3 - "$SPIRIT_LEVEL_DIR/log.jsonl" <<'PYEOF'
import json, sys
ok = bad = 0
events = set()
for line in open(sys.argv[1]):
    try:
        e = json.loads(line)
    except json.JSONDecodeError:
        bad += 1; continue
    if all(k in e for k in ("ts","session","model","event","rule","detail","cwd")):
        ok += 1; events.add(e["event"])
    else:
        bad += 1
print(f"valid={ok} bad={bad} events={sorted(events)}")
PYEOF
)
check "every log line well-formed" "bad=0" "$OUT"
for ev in route deny bypass advisory edit-loop; do
    check "  logged: $ev" "$ev" "$OUT"
done

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "ALL PASS — $PASS assertions"
else
    echo "RESULT: $PASS passed, $FAIL FAILED"
fi
exit "$FAIL"
