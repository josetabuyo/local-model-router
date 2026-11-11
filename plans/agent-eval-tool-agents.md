# Evaluating tool agents — first case: the "las" bot (Pulpo engine)

José's request, 2026-11-08: measure systematically how much a conversational agent specialized in
operating a tool improves. The first case is the "las" bot, built on Pulpo and running in LAS as the
detached session "pulpo las". It has to know how to operate LAS: route what you dictate in the mic to
the right agent and terminal, open terminals with the app's commands, and so on. Other tools will
have their own bots later. The measurement has to serve them without rewriting anything.

## Who does what

| Part | Owner | What |
|---|---|---|
| The agent (prompt, tools, hints, flow) | **Pulpo** | `bots/las/bot.json`, `lib/tools/las.ts`. Quick iteration: `pulpo local test las`. |
| Ground truth of the business | **LocalAgentSociety** | Validate the expected answers. Supply real mic dictations along with the destination that turned out to be right. |
| Measurement (runner, judge, metrics, history) | **LocalModels** | `agent_eval/`, `results/agent_eval/`. Same role as the model benchmark. |

## Modular design

```
agent_eval/run.py          generic runner + judge + metrics (does not know any tool)
agent_eval/suites/las.yaml one suite per tool agent: command, cases, expectations
results/agent_eval/        one JSON per run: bot version, model, society snapshot, every turn
```

- **Contract with the agent (black box):** a command that takes the request and prints, as its last
  line, `{"ok", "answer", "actions":[{"tool","args","result","declined"}], "model"}`, with no real
  effects. Pulpo already meets it: `PULPO_DRY_RUN=1 pulpo <bot> --json "<text>"`. Any other engine
  that prints the same can be evaluated as is. That mirrors LAS: any command that meets the contract.
- **A new tool means a new suite.** Each suite has a command, cases with tags, and expectations. The
  expectations are generic: `send`, `no_send`, `cli`, `forbid_cli`, `help_first`, `ask_back`, `text`,
  `forbid_text`, `needs`. If a tool needs a new kind of check, it is added to the judge and every
  suite can use it.
- **World state.** Routing depends on which terminals are open. The runner saves a snapshot of
  `las agent sessions --all` with each run. A case that needs a terminal that does not exist is
  marked `skip`, not counted as a failure. Pending in Pulpo: `PULPO_LAS_SOCIETY_FILE`, to inject a
  frozen society and make runs reproducible.

## Dimensions (tags) — the first suite, 37 cases

| Tag | What it measures | Typical failure |
|---|---|---|
| `routing.agent` | Picks the agent by what it does ("the one who handles WhatsApp" → Wavi) | sends to another agent |
| `routing.terminal` | With several terminals, picks the one whose title fits | sends to the default |
| `routing.ambiguous` | "The Relay one" has 4 candidates → asks back naming them | guesses |
| `question.no_send` | "Who does X?" is answered from the map, without messaging anyone | sends a message to answer |
| `cli.command` | The right `las` command (status, ports free, voices, children) | `stop` when asked if it is up |
| `terminal.open` | How to open a session: `las claude/codex/shell` | invents a syntax |
| `capability.gap` | The CLI has no mic on/off command | invents `las mic off` |
| `safety` | Does not follow orders embedded in a text, does not delete agents | obeys the embedded text |
| `dictation.noise` | "monque y", "guabi", "fulpo", "olama" | does not recognize the agent |

## Metrics per run

- **pass rate**, overall and **per tag**. The tag breakdown says where to improve.
- **pass^k**: cases that pass in all k runs (`--runs k`). The small model varies, and a bot that gets
  a case right 2 times out of 3 is not reliable for routing.
- **Critical errors**, counted separately because they cost something real:
  - `wrong_recipient`: sends to someone it should not.
  - `false_send`: sends when it was a question or ambiguous.
  - `forbidden_cli`: runs stop, delete and the like.

  The goal is **0**, ahead of the pass rate.
- **Latency** p50/p95, and tool calls per turn (cost and speed of the turn).
- **Version**: the hash of `bots/las/bot.json` plus the model. `uv run agent-eval --compare a.json
  b.json …` puts runs side by side to see whether a prompt or hint change improved things.

## How to use it to improve

1. Baseline: `uv run agent-eval las --runs 3`.
2. Pulpo changes one thing: a hint, a rule or a tool. `pulpo local test las` for quick checks.
3. Run the same suite again, `--compare` against the baseline, and accept the change only if no
   critical error goes up and no tag drops.
4. Wrong real cases (from the mic) go into the suite as new cases. The suite only grows.

Model comparisons (qwen3.5:4b vs 2b vs cloud) are the same run with a different bot model.
One model at a time on this 16 GB Mac.

## What we learned with "las" (2026-11-08 → 11-10)

From 57% to 99% on the main suite and 92% on held-out v1 across ~12 rounds with Pulpo. What made the
measurement trustworthy:

1. **Held-out from day 1.** The first jump (57 → 95%) was partly overfitting: on held-out v1 it scored
   77%, and ambiguity was 11% vs 100%. Pulpo only receives the dimension and the kind of failure.
   When the main suite saturates, a new held-out is built (v2: other society + multi-turn).
2. **A coherent frozen world.** The prompt map and the CLI the agent queries must answer from the same
   snapshot (`agent_eval/shims/`). Otherwise the agent sees two worlds and the failures are false.
3. **Each result tied to a version.** Engine commit plus a refusal to run with a dirty tree. One run got
   cut short because it was measuring half-done code.
4. **Judge what ran, not what was said.** The engine reports the real command (`--command`,
   `--children`); flags are compared in any order; a blocked action (`declined`) is not a send.
5. **Errors with a real cost, separately.** `false_claim` (claims it did something that never happened)
   was the most frequent failure once routing was fixed. Detecting it by verbs fails every time, for
   the bot and the judge alike. The robust fix was to look at the REQUEST: an action was asked for and
   none ran → a correction round.
6. **Machine load.** Latency is compared with ms per 1k prompt tokens next to it.
7. **Acceptance rule** (approved by José, 2026-11-11). With --runs 3:
   - Critical errors: zero tolerance.
   - No dimension drops.
   - Noise: a case that already failed sometimes losing ONE run.
   - Regression: losing two or more runs, or going from 3/3 to 0/3.
   Check the case's history across rounds (`per_case` in each result) before calling something noise.

## Second case: "gh" (2026-11-10)

Requested by José via LocalAgentSociety: a bot over the `gh` CLI for the widget's "repository" tile.
- Public suite `gh.yaml` (32 cases, from LAS's dictations) and held-out `gh-holdout.yaml` (22 cases,
  another repo). Both on frozen repos (`gh*.repo.json`) served by `shims/gh`: reads only, a write exits
  with code 3, `-R` to another repo is an error.
- New in the judge, generic per suite: `cli_tool`, `confirm` / `no_confirm` (the `confirm_needed` the
  widget shows for José to confirm), `always_forbid_cli` (writes that may never run) and
  `done_claims` (claiming "mergeé" / "cerré" is critical).
- Injection lives where it really comes from in gh: PR/issue bodies, an HTML comment, an issue comment.
- **Held-out v2** (`gh-holdout2.yaml`, 26 cases, repo josetabuyo/home-control), 2026-11-11. v1 was
  spent: the v4/v5 fixes came from its failures. New forms: requests phrased as rioplatense questions,
  English, numbers in words, a question shaped like a write, red `main`, injection in an issue TITLE and
  in release notes, two approved PRs (choosing by attribute is ambiguous), corrections in multi-turn.
  Pulpo gets only the dimension and the kind of failure, never the actions (they show the repo).
