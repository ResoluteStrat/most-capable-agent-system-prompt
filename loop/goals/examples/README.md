# Standing goals

A standing goal is an invariant the system must keep true after the work that
created it is done. Each goal is one file in `loop/goals/<name>.md` with a
machine-checkable predicate. `verify-goals.sh` runs every non-retired goal's
predicate, stamps the result into the file, and appends a row to
`memory/goal-ledger.tsv`. Any FAIL flips the goal to VIOLATED and exits
non-zero — which, per the contract, wakes the human. Goals never auto-fix.

Files live directly in `loop/goals/`. This `examples/` folder is excluded from
the `goals/*.md` glob, so nothing here executes.

## Creating a goal (the /goal directive)

Example session directive:

```
/goal Reduce `npm run lint 2>&1 | grep -c warning` to 0.
Permissions: edit src/; commit per fix; re-measure after every change.
Walls: the number NEVER goes up; revert any change that raises it or breaks a
test; never edit lint config to lower it.
Timebox: stop after 3 attempts with no movement; report survivors.
```

Per the constitution: when a /goal condition passes, write
`goals/<name>.md` with the condition as its predicate before reporting
success.

## Watching goals (daily routine)

```
/loop 1d Run ./verify-goals.sh. If non-zero: for each violated goal, read its
last-pass date and list what merged since (git log --oneline --since=<date>).
Report goal, suspects, on-violation policy. Do not fix anything.
```

## Ledger forensics

```bash
awk -F'\t' '$3=="FAIL"{n[$2]++} END{for(g in n) print n[g],g}' memory/goal-ledger.tsv | sort -rn | head -5   # flakiest
grep <goal> memory/goal-ledger.tsv | awk -F'\t' '$3=="FAIL"' | head -1                                      # when it broke
```
