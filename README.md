# sieve

Every conversation you have with Claude Code about a project teaches it something: a convention you corrected, a library that turned out to be a bad fit, the one command that actually starts the dev server. Then the conversation ends and the next person, or the next session, starts from zero.

`/sieve` reads the conversations you have had about the current repository, keeps the few lessons worth sharing, and, after you approve them, writes them to a skill inside the repo. Commit that file and every teammate's Claude reads it.

## Install

In Claude Code:

```
/plugin marketplace add rodrigosnader/sieve
/plugin install sieve@sieve
```

Requires Python 3 (standard library only).

## Use

Open Claude Code in any repository and run:

```
/sieve
```

1. **Scan.** Finds this repo's conversations on your machine (including its worktrees), and keeps only what people and Claude wrote to each other. Tool output, file dumps and screenshots are dropped, which is usually over 99% of the weight. Sessions opened by an app or a script through the Agent SDK or `claude -p` are skipped.
2. **Read.** Splits the new text into batches and reads them in parallel with a small, cheap model (Haiku), which returns candidate lessons.
3. **Select.** Your session's model compares the candidates with what the repo already has, merges duplicates, drops anything too specific to one task, and rewrites each survivor as the general rule its evidence supports.
4. **Review.** You see each proposal with the quote it came from, and pick what to keep.
5. **Write.** Kept items go to `.claude/skills/project-learnings/SKILL.md`, and a one-line summary of each conversation goes to `conversations.md` next to it. Nothing is committed for you.

Run it again any time. Only text written since the last run is read, and a conversation that continued after the last run is read from where it stopped.

## Run it automatically

```
/sieve --attach
```

From then on, every time you start a Claude Code conversation in this repository, sieve checks in the background for conversations it has not read and does steps 1 to 3 on its own. When it has proposals, your next conversation tells you, and `/sieve` takes you straight to the review. Nothing reaches the repo without your review.

`/sieve --detach` turns it off. `/sieve --status` says what is pending.

Attaching is per person and per repository, and is stored on your machine, not in the repo.

## The conversations log

`conversations.md` is a markdown table with one row per conversation: date, id, who had it, and one sentence on what was worked on and how it ended. It is plain markdown so it reads as a table on GitHub, Claude reads it directly, and each conversation is one line in a git diff. A conversation that continues later gets its row updated, not a new one.

## What it keeps

Two kinds of lessons, and only when someone else working on the repo would otherwise make the same mistake or ask the same question:

- **Rules:** conclusions a person reached, such as a correction, a convention, or a decision with its reason.
- **Insights:** things Claude learned while working, with proof in the conversation. An approach failed for a stated reason and the alternative worked, or a fact about the environment was found by running something.

It leaves out task-specific details, progress reports, anything the code or git history already says, secrets, and one person's personal taste. Personal items are counted and offered separately; they never go in the repo.

There is no quota. Most conversations produce nothing, and that is the expected result.

## Where things live

| What | Where | Shared |
|---|---|---|
| Your conversations | `~/.claude/projects/<repo path with / replaced by ->/` | No, stays on your machine |
| Which conversations sieve has read | `~/.claude/sieve/state/` | No |
| Condensed batches of each run | `~/.claude/sieve/runs/` | No |
| Whether this repo is attached | `~/.claude/sieve/state/` | No |
| The learnings | `<repo>/.claude/skills/project-learnings/SKILL.md` | Yes, through git |
| The conversations log | `<repo>/.claude/skills/project-learnings/conversations.md` | Yes, through git |

Each teammate runs `/sieve` on their own conversations. The learnings file is the shared part, reviewed like any other change.

## License

MIT
