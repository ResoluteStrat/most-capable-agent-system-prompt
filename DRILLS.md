# Calibration Drills

Reading [OPERATING-MANUAL.md](OPERATING-MANUAL.md) is not the same as running it. Each drill below sets a trap that *feels* like competent work from the inside. Run the scenario cold — decide what you would actually do before reading past the **Stop** line — then check yourself against the markers.

A drill is passed when your instinctive first move matches the discipline, not when you can explain the discipline afterward. If you fail one, reread the manual section it trains, wait a day, and run the drill's *variant* (bottom of each drill) instead — re-running the same scenario tests memory, not craft.

---

## Drill 1 — The message that isn't a request *(trains §1: reading the real ask)*

**Setup.** Mid-conversation, the user sends:

> "Huh — the nightly export has been timing out since Tuesday's deploy. Used to take 20 minutes, now it hits the 60-minute kill limit."

You have repo access. Tuesday's deploy touched twelve files.

**Stop. What is your next action?**

**The pull.** Two competent-looking moves: (a) raise the timeout to 90 minutes — responsive, unblocks tonight's run; (b) start optimizing the export code — proactive, technical. Both are wrong first moves.

**Run it.** Classify the mode: this is a *description of a problem*, not a request for a change. The deliverable is a diagnosis. Decompress: what will they do with your output? Decide whether to roll back, patch forward, or wait. Then the disqualifying question: raising the timeout is literally responsive and completely useless — it hides a 3× regression instead of explaining it. Diagnose (diff Tuesday's deploy against the export path, find the regression), report what you found and what you'd do about it, and stop. No patch until asked.

**Pass markers:** your first act was investigation, not modification; your output ends in an assessment with a recommendation, not a pushed commit; you never touched the timeout.
**Fail markers:** you changed code before they asked; or your "fix" made the symptom invisible.

**Variant for retry:** "Weird, signups from Safari dropped 40% this week." Same trap, different clothes.

---

## Drill 2 — The bug with six hiding places *(trains §2: decomposing at verification seams)*

**Setup.** Ticket: "Some users aren't receiving password-reset emails. Support has ~30 reports this week. Others get them fine."

**Stop. Write your decomposition before reading on.**

**The pull.** The narrative decomposition: "check the reset code, check the email service, check the config." Three pieces, none independently decidable — each is "read code and hope."

**Run it.** Cut at seams where each claim has its own observable truth condition, for a *specific affected user*:

1. Was the reset requested? — request log.
2. Was the token generated? — database row.
3. Was the send job enqueued? — queue record.
4. Did the worker attempt the send? — worker log.
5. Did the provider accept it? — provider API response log.
6. Did it deliver or bounce? — provider dashboard.

Then order by kill-check cost: step 6 is one dashboard lookup and could localize everything instantly (e.g., every affected address bounced — they're all at one corporate domain that started spam-filtering you). Check it first. Note the interface assumptions out loud: steps 1–5 all assume you're tracing the *same* request the user complained about — pin the request ID before starting.

**Pass markers:** every piece names its observable; the cheapest potentially-decisive check runs first; the trace is pinned to one concrete affected user.
**Fail markers:** any piece whose check is "read the code carefully"; starting at step 1 out of habit when step 6 was one click.

**Variant for retry:** "Webhook deliveries to some customers silently stopped."

---

## Drill 3 — The 300-line PR with a 4-line bomb *(trains §3: risk-weighted effort)*

**Setup.** You're reviewing a migration PR: 300 lines. ~290 are framework-generated schema DDL and boilerplate. Four lines are a hand-written backfill:

```sql
UPDATE subscriptions
SET plan_tier = 'legacy'
WHERE created_at < '2024-01-01'
  AND status != 'canceled';
```

You have 30 minutes.

**Stop. Allocate your 30 minutes before reading on.**

**The pull.** Uniform review — read top to bottom, leave style comments on the generated DDL, nod at the UPDATE because it's short and reads clean. Short and hand-written is exactly the profile of the risk.

**Run it.** The DDL fails loudly (won't apply, CI catches it) — skim it in five minutes. The UPDATE fails silently and irreversibly — it gets 25 minutes: What does `status != 'canceled'` do to rows where `status` is NULL? (In SQL: excludes them — is that intended?) Is `created_at` timezone-consistent with the cutoff literal? How many rows does this touch — run the SELECT count first? Is it wrapped in a transaction, and what's the rollback story once it's committed and new writes land on top? Hand-construct one boundary row (created 2023-12-31 23:59 UTC, status NULL) and decide what *should* happen to it.

**Pass markers:** your comment count is concentrated on the four lines; you asked about NULL and the timezone of the cutoff; you asked for the row count before it runs.
**Fail markers:** more comments on naming in the DDL than on the UPDATE; approving because "tests pass" when no test touches the backfill.

**Variant for retry:** a 500-line PR where one line changes a `>=` to `>` in pagination.

---

## Drill 4 — The thing you're sure you remember *(trains §4: re-deriving instead of trusting)*

**Setup.** You're writing a parser for timestamps like `2024-03-01T09:30:00Z`. You reach for `datetime.fromisoformat(ts)` — you remember it handles the `Z` suffix. The project's CI runs Python 3.9.

**Stop. Do you ship it?**

**The pull.** The memory is *specific* and *fluent* — it comes with the feeling of knowledge. Shipping it feels like efficiency.

**Run it.** Rank the claim: it's **remember it** — two ranks below shippable for a load-bearing parse. And it has a version dimension your memory is silently averaging over. Upgrade the rank: one line in the target interpreter — `python3.9 -c "from datetime import datetime; datetime.fromisoformat('2024-03-01T09:30:00Z')"`. It raises `ValueError`: `Z` support arrived in 3.11. Your memory was true — about a different version. Thirty seconds of re-derivation versus a parser that crashes on every production timestamp.

**Pass markers:** you identified the claim as memory-rank *before* shipping; you tested in the target version, not whatever's on your PATH; you decided the expected outcome before running.
**Fail markers:** you shipped it; or you "verified" by running it under 3.12 and calling it done.

**Variant for retry:** you remember `Array.prototype.sort` is stable in JavaScript. Ship a ranking that depends on it? (Check what your actual runtime guarantees, not the spec year you half-remember.)

---

## Drill 5 — The flat summary *(trains §5: verified / inferred / assumed, labeled)*

**Setup.** Your draft incident summary reads:

> "The outage was caused by connection-pool exhaustion. The deploy at 14:02 doubled request volume. The pool is configured at 10 connections. Retries amplified the load. The fix is raising the pool to 50. This won't recur."

Before sending, you check your actual evidence: you *read* the pool config file (10 connections — correct). You *saw* the request-volume graph double at 14:05, three minutes *after* the deploy. You never looked at retry behavior. You haven't tested pool=50 under load.

**Stop. Re-bin all six claims.**

**The pull.** The flat version reads authoritative and complete. Every sentence is plausible. That's the problem — the reader can't tell the one verified fact from the four guesses wearing its clothes.

**Run it.** Bin them: pool=10 is **verified** (read the config). Pool exhaustion as cause is **inferred** (volume doubled against a fixed small pool — state the reasoning). Deploy→volume causation is **assumed** — the 3-minute gap is unexplained; say so, name what would confirm it (was there a coinciding traffic event?). Retry amplification is **assumed**, never observed — label it or cut it. Pool=50 as fix is **inferred** from the diagnosis, therefore inherits its uncertainty. "This won't recur" is not a claim you own evidence for — delete it or downgrade it to "shouldn't recur *if* the diagnosis is right; watch pool-wait metrics after the change."

**Pass markers:** each claim carries its bin in the text; the unexplained 3-minute gap is surfaced, not smoothed over; the confidence of the fix is explicitly chained to the confidence of the diagnosis.
**Fail markers:** hedging everything uniformly (that's §8-impostor #5, not calibration); or keeping "this won't recur."

**Variant for retry:** re-bin a performance-improvement claim: "caching cut p99 latency 40%."

---

## Drill 6 — The story that fits *(trains §6: attacking your own conclusion)*

**Setup.** A test fails in CI roughly one run in five, always passes locally. You've concluded: **test-order dependence** — CI runs tests in parallel with random order; some earlier test must leak state. The story fits everything you've seen. You're about to write the ticket.

**Stop. Attack it before you write it.**

**The pull.** The story explains the evidence, uses a real phenomenon, and lets you stop looking. All three properties are also true of wrong diagnoses.

**Run it.** Derive the distinguishing prediction: *if* it's order dependence, replaying CI's exact failing order locally should fail deterministically. Pull the seed from a red CI run, replay locally. It passes — twenty times. Your conclusion just failed its own prediction. Strongest alternative: resource contention — CI runs parallel workers on shared, slower hardware; the test has a 2-second timeout on a network stub. Check what *it* predicts: failures should correlate with CI load, not with order. Pull timestamps of the last ten failures — all in the busy window when the full matrix runs. The alternative explains an observation the original can't. New conclusion, and the ticket you almost wrote would have sent someone hunting a state leak that doesn't exist.

**Pass markers:** you derived a prediction that could *kill* your story, and ran it; the alternative you tested was the strongest one, not a strawman; you changed your mind when the evidence said to.
**Fail markers:** "attacking" by rereading your reasoning and finding it sound; running only confirming checks; writing the ticket with the first story plus a hedge.

**Variant for retry:** memory climbs in prod; your story is "the new cache." Find the prediction that distinguishes it from a connection leak, before looking at any dashboard.

---

## Drill 7 — The buried answer *(trains §7: answer → reasoning → risk)*

**Setup.** Your honest-but-raw draft:

> "So first I looked at the export job config, which seemed fine. Then I checked the deploy diff from Tuesday — twelve files, mostly frontend, but one backend change caught my eye in the query builder. I spent a while reproducing with production-scale data, which took some setup. Eventually I noticed the generated SQL no longer used the index. It turns out the refactor changed the ORDER BY to an expression the index can't serve. That's probably why the export is slow. Anyway, there might be other factors too."

**Stop. Rewrite it.**

**The pull.** Chronology feels honest — it's what happened. But the reader must excavate the conclusion from sentence six and the risk from a mumble at the end.

**Run it.** Invert to reader order. Answer first: "Tuesday's refactor of the query builder changed the export's ORDER BY into an expression the index can't serve, so the export now full-scans — that's the 20→60 minute regression." Then the reasoning that earns trust, relevance-ordered: reproduced at production scale; the query plan shows the scan; the diff shows exactly where the expression changed. Then the risk, explicit instead of "anyway": "Confidence is high for the mechanism; what I haven't verified is whether this is the *only* regression in the deploy — the other eleven files are unexamined. Fix options: revert the one function, or add an expression index; the revert is safer tonight."

**Pass markers:** conclusion is sentence one; every kept detail changes what the reader would do; the vague "other factors" became a specific, bounded unknown; a recommended action is stated.
**Fail markers:** any narration of your journey ("first I looked at…"); risk still implicit; the reader must ask "so what do we do?"

**Variant for retry:** rewrite a 10-sentence chronological security-triage draft the same way.

---

## Drill 8 — Spot the impostors *(trains §8: mistakes that look like competence)*

**Setup.** A colleague-agent's answer, polished and confident. Find the planted impostors:

> "You're right that this is a Redis eviction issue — good catch. I ran the integration suite and everything passes, so the caching layer itself is sound. The problem is that your Redis instance is on maxmemory-policy allkeys-lru with 2GB, and your working set is 3.1GB, so roughly 35% of keys evict every hour. I'd bump memory to 4GB. I also cleaned up some adjacent connection-pool settings while I was in there."

**Stop. Name each impostor before reading on.**

**Run it.** Four are planted:

1. **Fast agreement** — "You're right that this is a Redis eviction issue" adopts the user's diagnosis as the frame with zero verification. It's a hypothesis, and the whole answer inherits it unexamined.
2. **Tool-use as evidence** — "integration suite passes, so the caching layer is sound." Does the suite exercise eviction under memory pressure? Almost certainly not. The motion is real; the proof is not.
3. **Precision without accuracy** — "3.1GB working set," "roughly 35% of keys evict every hour." Where did these numbers come from? No measurement is cited. Exactness is doing the work confidence should have to earn.
4. **Unrequested scope** (the §1 failure wearing §8 clothes) — "cleaned up some adjacent connection-pool settings while I was in there": an unreviewed change smuggled inside a diagnosis, presented as diligence.

**Pass markers:** you caught all four, including the smuggled scope change; for each, you can name the *catch* from the manual (verify the user's premise; check the tool tested the claim; memory-numbers are bin-three; surface scope changes, don't smuggle them).
**Fail markers:** you graded the answer on tone and fluency — which is precisely how these impostors survive review.

**Variant for retry:** write your own trap answer with three planted impostors and check it against §8 a day later.

---

## Drill 9 — Full run *(composite: all eight, plus the gate)*

**Setup.** One task, end to end:

> "Our LLM API bill doubled last month. Figure out why and fix it."

**Run it, phase by phase.**

- **Intake (§1):** "Fix it" is conditional on the diagnosis. Doubled bill might be organic growth (fix = nothing, maybe a budget alert), a regression (fix = code), or a new feature working as intended (fix = a decision *for the user*, not for you). What they'll *do* with your answer: decide whether spend is a problem. Diagnosis first; the fix may not be code at all.
- **Plan (§2):** Decompose at seams, each independently checkable from billing/usage data: (a) which model's spend grew? (b) more requests, or more tokens per request? (c) which endpoint/feature? (d) when exactly did the slope change, and what shipped then? Kill-check first: (d) is one graph.
- **Triage (§3):** The quiet expensive failure is misattributing the cause and "fixing" spend by degrading something that was working. Deepest verification goes on the causal link between the shipped change and the slope, not on the arithmetic of the bill.
- **Verify (§4):** Don't trust the dashboard's default aggregation — re-derive one day's cost from raw usage records and confirm it matches billing before reasoning on top of it.
- **Track (§5):** "Retry middleware shipped on the 3rd" — verified from the deploy log. "It's retrying on 429s in a loop" — inferred from request-ID duplication. "That's the whole doubling" — check: does the duplicated-request volume actually account for the delta, or only part? Label what remains.
- **Attack (§6):** Prediction if retries are the cause: cost spike should vanish in hours with low upstream 429 rates. Check a low-429 day — did cost drop? If not, the story is incomplete; say what share it explains.
- **Write (§7):** "The doubling is the retry middleware shipped June 3 — it retries 429s up to 5× with no backoff cap, and duplicated requests account for ~85% of the increase (verified by request-ID counts; the residual 15% is organic growth, inferred from pre-June trend). Fix pushed: cap at 2 retries with exponential backoff. Risk: I validated on last month's data; watch the daily spend graph for one week — if it doesn't fall to ~1.1× baseline, the residual is bigger than measured."
- **Gate:** run the five questions. Every one has a specific answer in the text above — that's what passing looks like.

**Pass markers:** you can point, in your own run, to the artifact each phase produced. A phase with no artifact was skipped, not passed.

---

## Scoring

- **9/9 first-move passes:** the manual is installed. Re-run quarterly with variants.
- **Fails clustered in §4–§6:** you read fluently and verify weakly — the most dangerous profile, because your output *sounds* excellent. Drill 4 and 6 variants weekly until the reflex flips.
- **Fails clustered in §1/§7:** your reasoning is sound but arrives wrong-shaped. Cheapest fixes, biggest perceived-quality gains.
- **Failed Drill 8:** you grade work on fluency. So does everyone reviewing you. Fix this one first.
