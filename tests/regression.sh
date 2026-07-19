# Regression cases from the adversarial review. Sourced by run.sh, which
# supplies check/check_no/run_hook/bash_pay/pay/write_config and the fixtures.
#
# Every case here is a defect that shipped, or nearly shipped, and was found by
# a reviewer with no prior context rather than by the author.

echo "== regression: per-target safe-path checking =="
# SAFE_TARGET is matched against the extracted write target, never the whole
# command. Matching the command let any stray safe-looking word whitelist it.
run_hook "$(bash_pay r1 "$CLEAN" "echo '$FAKE_KEY' > /tmp/evil.js # see secrets.md")" "$H/guard.py"
check "trailing comment cannot whitelist" "[G3]" "$OUT"
run_hook "$(bash_pay r1 "$CLEAN" "echo '$FAKE_KEY' > /tmp/evil.js && rm -f credentials")" "$H/guard.py"
check "second clause cannot whitelist" "[G3]" "$OUT"
run_hook "$(bash_pay r1 "$CLEAN" "echo 'K=$FAKE_KEY' > .env && echo '$FAKE_KEY' > public/config.js")" "$H/guard.py"
check "one safe target does not cover an unsafe one" "[G3]" "$OUT"

echo "== regression: printing a secret stays allowed =="
# >>?\s*\S used to match =>, ->, and 2>&1, so merely printing a key was denied.
run_hook "$(bash_pay r2 "$CLEAN" "echo 'use $FAKE_KEY => in the header'")" "$H/guard.py"
check "=> is not a redirect" "-" "$OUT"
run_hook "$(bash_pay r2 "$CLEAN" "echo 'the key $FAKE_KEY -> goes to Vault'")" "$H/guard.py"
check "-> is not a redirect" "-" "$OUT"
run_hook "$(bash_pay r2 "$CLEAN" "echo '$FAKE_KEY' 2>&1")" "$H/guard.py"
check "2>&1 is not a write" "-" "$OUT"

echo "== regression: write primitives beyond > >> tee =="
OUT=$(bash_pay r3 "$CLEAN" "python3 -c \"open('/tmp/a.js','w').write('$FAKE_KEY')\"" | python3 "$H/guard.py")
check "python open().write denied" "[G3]" "$OUT"
run_hook "$(bash_pay r3 "$CLEAN" "sed -i 's|X|$FAKE_KEY|' /tmp/a.js")" "$H/guard.py"
check "sed -i denied" "[G3]" "$OUT"
run_hook "$(bash_pay r3 "$CLEAN" "perl -pi -e 's/X/$FAKE_KEY/' /tmp/a.js")" "$H/guard.py"
check "perl -pi denied" "[G3]" "$OUT"
run_hook "$(bash_pay r3 "$CLEAN" "echo '$FAKE_KEY' | sponge /tmp/a.js")" "$H/guard.py"
check "sponge denied" "[G3]" "$OUT"

echo "== regression: git -C must not bypass G1/G2 =="
# The flag run in DESTRUCTIVE_GIT excluded '/', so an absolute -C path slipped.
run_hook "$(bash_pay r4 "$DIRTY" "git -C $DIRTY reset --hard HEAD~1")" "$H/guard.py"
check "git -C does not bypass G1" "[G1]" "$OUT"
run_hook "$(bash_pay r4 "$CLEAN" "git -C /tmp/x commit -m 'f

Co-Authored-By: Claude <n@a.com>'")" "$H/guard.py"
check "git -C does not bypass G2" "[G2]" "$OUT"
run_hook "$(bash_pay r4 "$DIRTY" "git stash clear")" "$H/guard.py"
check "stash clear denied like stash drop" "[G1]" "$OUT"

echo "== regression: config type abuse fails toward enforcement =="
# A string iterates character by character; "c" matched every model as native.
write_config '{"native_models":"claude-fable"}'
run_hook "$(pay r5 "$OTHER_T" "$CLEAN" "")" "$H/protocol-inject.py"
check "string native_models does not mark everyone native" "BASELINE" "$OUT"
# A non-string entry raised, killing the hook and the confirm block with it.
write_config '{"native_models":[123]}'
run_hook "$(pay r6 "$OTHER_T" "$CLEAN" "")" "$H/protocol-inject.py"
check "non-string native_models does not crash the hook" "STOP AND CONFIRM FIRST" "$OUT"
# `null` is not `false`: cfg.get(k, True) returned None and silently disabled.
write_config '{"confirm_first":null}'
run_hook "$(pay r7 "$NATIVE_T" "$CLEAN" "")" "$H/protocol-inject.py"
check "confirm_first null keeps the block" "STOP AND CONFIRM FIRST" "$OUT"
write_config '{"guards":"nonsense","advisories":42,"remote_pins":"x"}'
run_hook "$(bash_pay r8 "$DIRTY" "git reset --hard HEAD~1")" "$H/guard.py"
check "garbage guard types fall back to enforcing" "[G1]" "$OUT"
write_config '[]'
OUT=$(bash_pay r9 "$DIRTY" "git reset --hard HEAD~1" | python3 "$H/guard.py" 2>/dev/null)
check "non-object config root falls back to enforcing" "[G1]" "$OUT"

echo "== regression: fd-prefixed and clobber redirects (2nd review) =="
# The lookbehind that made 2>&1 safe also excluded 1> — the plain redirect
# with an explicit fd — leaving G3 fully bypassable.
run_hook "$(bash_pay r11 "$CLEAN" "echo '$FAKE_KEY' 1> /tmp/steal.txt")" "$H/guard.py"
check "1> is a write" "[G3]" "$OUT"
run_hook "$(bash_pay r11 "$CLEAN" "echo '$FAKE_KEY' 2> /tmp/steal.txt")" "$H/guard.py"
check "2> is a write" "[G3]" "$OUT"
run_hook "$(bash_pay r11 "$CLEAN" "echo '$FAKE_KEY' &> /tmp/steal.txt")" "$H/guard.py"
check "&> is a write" "[G3]" "$OUT"
run_hook "$(bash_pay r11 "$CLEAN" "echo '$FAKE_KEY' 1>> /tmp/steal.txt")" "$H/guard.py"
check "1>> is a write" "[G3]" "$OUT"
run_hook "$(bash_pay r11 "$CLEAN" "echo '$FAKE_KEY' >| /tmp/steal.txt")" "$H/guard.py"
check ">| clobber is a write" "[G3]" "$OUT"
# ...but pseudo-devices are not storage.
run_hook "$(bash_pay r12 "$CLEAN" "curl -H 'Authorization: Bearer $FAKE_KEY' https://x.test 2>/dev/null")" "$H/guard.py"
check "2>/dev/null is not a write" "-" "$OUT"
run_hook "$(bash_pay r12 "$CLEAN" "echo '$FAKE_KEY' > /dev/null")" "$H/guard.py"
check "/dev/null is not storage" "-" "$OUT"

echo "== regression: quoted text is data, not an instruction =="
run_hook "$(bash_pay r13 "$DIRTY" "git commit -m 'reverted the git clean -fd change'")" "$H/guard.py"
check "commit message quoting a destructive cmd is not G1" "-" "$OUT"
run_hook "$(bash_pay r13 "$DIRTY" "echo 'never run git reset --hard here'")" "$H/guard.py"
check "echoing a destructive cmd is not G1" "-" "$OUT"

echo "== regression: SAFE_TARGET is anchored, not a substring =="
run_hook "$(bash_pay r14 "$CLEAN" "echo '$FAKE_KEY' > public/credentials.js")" "$H/guard.py"
check "credentials.js in a web dir still denied" "[G3]" "$OUT"
run_hook "$(bash_pay r14 "$CLEAN" "echo '$FAKE_KEY' > my-credentials-backup.txt")" "$H/guard.py"
check "substring 'credentials' does not whitelist" "[G3]" "$OUT"
run_hook "$(bash_pay r14 "$CLEAN" "echo 'K=$FAKE_KEY' > server/.env.production")" "$H/guard.py"
check "genuine .env.production still allowed" "-" "$OUT"
run_hook "$(bash_pay r14 "$CLEAN" "echo '$FAKE_KEY' > certs/server.pem")" "$H/guard.py"
check "genuine .pem still allowed" "-" "$OUT"

echo "== regression: G1 covers checkout -f =="
run_hook "$(bash_pay r15 "$DIRTY" "git checkout -f main")" "$H/guard.py"
check "checkout -f discards WIP, denied" "[G1]" "$OUT"

echo "== regression: previously-vacuous assertions =="
# An opaque write primitive must fail CLOSED even when the command mentions a
# safe path, because the real target cannot be determined.
run_hook "$(bash_pay r16 "$CLEAN" "echo '$FAKE_KEY' | sponge .env")" "$H/guard.py"
check "opaque write fails closed despite safe-looking path" "[G3]" "$OUT"
# A string native_models is honored as ONE prefix, not iterated per character.
write_config '{"native_models":"claude-opus"}'
run_hook "$(pay r17 "$OTHER_T" "$CLEAN" "")" "$H/protocol-inject.py"
check_no "string native_models honored as a single prefix" "BASELINE" "$OUT"
write_config '{}'

echo "== regression: confirm_first off must not suppress the baseline =="
write_config '{"confirm_first":false}'
run_hook "$(pay r10 "$OTHER_T" "$CLEAN" "")" "$H/protocol-inject.py"
check "confirm off + non-native still gets baseline" "BASELINE" "$OUT"
check_no "  ...and the confirm block really is gone" "STOP AND CONFIRM FIRST" "$OUT"
write_config '{}'
