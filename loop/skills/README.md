# Skills — one file per employee

A skill is a stable, kebab-case identity the conductor assigns to work
(`"skill"` in the work order). The trust ledger (`memory/trust.tsv`) tracks
each skill's runs and pass rate; `scripts/trust-log.sh --tier <skill>` maps
that history to a tier:

- **auto**  — >=20 runs and >=95% pass rate. Work ships (PR opened) unattended.
- **queue** — proven but not trusted. Work lands in a worktree for human review.
- **watch** — <10 runs or <90% pass rate. Everything queues; repeated fails alert.

Add a file per recurring employee describing its mandate and walls. The two
sparring employees below ship as the starter pair.
