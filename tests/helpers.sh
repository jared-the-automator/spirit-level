# Assertion helpers, sourced by run.sh.

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

check_no() { # name, substring that must NOT appear, actual
    local name="$1" nope="$2" actual="$3"
    if printf '%s' "$actual" | grep -qF "$nope"; then
        echo "  FAIL  $name — '$nope' should be absent"; FAIL=$((FAIL+1))
    else
        echo "  PASS  $name"; PASS=$((PASS+1))
    fi
}

# Runs a hook and sets OUT. A crashing hook produces empty stdout, which is
# indistinguishable from "allowed" to a bare check — so the exit code is
# asserted here rather than silently discarded.
run_hook() { # payload_json, hook_path
    local payload="$1" hook="$2" rc
    OUT=$(printf '%s' "$payload" | python3 "$hook" 2>"$SCRATCH/err.txt")
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "  FAIL  hook $(basename "$hook") exited $rc: $(head -2 "$SCRATCH/err.txt" | tr '\n' ' ')"
        FAIL=$((FAIL+1))
    fi
}
