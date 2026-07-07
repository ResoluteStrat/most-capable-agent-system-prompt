predicate: cd $REPO && npm test -- tests/auth 2>&1 | tail -1 | grep -q passing
born: 2026-07-06
source: /goal session 2026-07-06 (fix auth flake)
status: satisfied
last-pass: 2026-07-06
on-violation: wake me. Do not auto-fix.
retire-when: auth module deleted. Retirement is a human decision, logged.
