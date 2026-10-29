---
name: sieve
description: Read this project's past Claude Code conversations that have not been read yet, log a one-line summary of each, extract the few rules and insights worth sharing, and propose them for the repo's shared sieve-learnings skill. Run with /sieve; /sieve --attach to do it automatically at every session start, /sieve --detach to stop.
argument-hint: "[--attach | --detach | --status]"
disable-model-invocation: true
---

# Sieve

Turn what people and Claude learned in past conversations about this repository into a short, shared skill that every teammate's Claude reads, plus a log of what each conversation was about. Bring little, and only what is high quality.

Talk to the user in the language they use with you.

The script used below is `python3 "${CLAUDE_PLUGIN_ROOT}/skills/sieve/scripts/sieve.py"`, called `sieve.py` here.

## Pick the mode from the arguments: `$ARGUMENTS`

- `--attach`: run `sieve.py attach --cwd "$PWD"`. Tell the user in one or two sentences: from now on, every time they start a Claude Code conversation in this repository, Sieve checks in the background for conversations it has not read; a single line at the top of the terminal shows when it is reading and when learnings are ready to review with /sieve. Nothing is written to the repo without their review. Stop.
- `--detach`: run `sieve.py detach --cwd "$PWD"`, confirm in one sentence, stop.
- `--status`: run `sieve.py status --cwd "$PWD"` and answer in one sentence. Stop.
- `--background <run dir>`: you were started by the hook with no person present. Do steps 2 and 3 for that run dir (its batches are the `batch-*.md` files in it; the learnings and log paths are `<repo>/.claude/skills/sieve-learnings/SKILL.md` and `conversations.md`). Then print ONLY the JSON object described in "Background output" and stop. Do not write files, ask questions or run commit.
- No arguments: the interactive run, below.

## 1. Scan

First run `sieve.py status --cwd "$PWD"`. If `proposed_run` is set, a background run already did steps 2 and 3: read `<proposed_run>/proposals.json`, use it as the result of step 3, take the paths from that run, and go to step 4.

Otherwise run `sieve.py scan --cwd "$PWD"`. It prints a JSON manifest: `learnings` (the shared skill file), `conversations_log`, `run`, `conversations`, `conversation_ids`, `batches` (markdown files holding only what people and Claude wrote; tool output is already stripped).

If `conversations` is 0, run `sieve.py commit "<run>"`, tell the user there is nothing new since the last run, and stop.

## 2. Read the batches

Launch one `sieve:reader` agent per batch, all in a single message so they run in parallel. Prompt each with just the absolute path of its batch file. If that agent type is unavailable, use `general-purpose` with `model: "haiku"` and paste the contents of `${CLAUDE_PLUGIN_ROOT}/agents/reader.md` (without its frontmatter) above the path.

Each returns `{"conversations": [...], "candidates": [...]}`. Collect them all.

## 3. Select

This is the step that decides quality. Do it yourself, carefully. Readers are generous; you are not.

1. Read the current learnings file and conversations log if they exist, and the repo's `CLAUDE.md` / `AGENTS.md` if they exist.
2. Drop candidates already covered there. If a candidate sharpens or contradicts an existing item, propose an edit to that item instead of a new one.
3. Merge candidates that say the same thing from different conversations. Repetition across conversations is the strongest signal that something matters.
4. Drop every candidate that fails either test: it applies to future tasks beyond the one it came from, and a teammate starting a new conversation on this repo would make a mistake or waste a round without it. Decisions about one screen or feature fail the first test unless they state a principle that covers others.
5. Rewrite each survivor as the general rule its evidence supports, in one or two plain sentences, with the reason when there is one.
6. Set `personal` candidates aside. They do not go in the repo.

There is no quota. How many survive depends on the conversations, and zero is a normal result.

## 4. Review with the user

Show the proposals as a numbered list, each as: the item, its kind (rule or insight), and in one short line where it came from (date and the evidence quote). Mark edits to existing items as edits and show old and new text. Then, in one line each: how many conversations will be added to the conversations log, and how many personal-preference items were set aside (offer to show them).

Ask which to keep. Accept answers like "all", "none", "all but 3", or edited wording.

## 5. Write

Write the kept items to the learnings file. Create it if missing, with this shape:

```markdown
---
name: sieve-learnings
description: Rules and lessons learned by people working on this repository with Claude. Read at the start of any task in this repository, before planning or writing code. conversations.md in the same folder logs what past conversations worked on.
---

# Project learnings

## Rules

- Rule text. Why, if known. (YYYY-MM-DD)

## Insights

- Insight text. Why, if known. (YYYY-MM-DD)
```

Keep items short. Put the date the item was learned at the end so stale insights can be reviewed later. Edit existing items in place; never duplicate.

Then add the conversations to the log (unless the user said not to). Create it if missing:

```markdown
# Conversations

One line per Claude Code conversation about this repository, newest first. Written by Sieve.

| Date | Conversation | Who | Summary |
|---|---|---|---|
| 2026-10-21 | 3f2a91c0 | Ana | Moved the comment tools into the Comments tab; shipped to dev. |
```

`Who` is `git config user.name` in the repo. Insert new rows under the header, newest first. If a conversation id is already in the table (it continued after the last run), update that row's summary to cover both parts instead of adding a row. Escape `|` in summaries.

Do not commit; tell the user which files changed so they can review the diff and commit them with their team.

## 6. Mark as read

After the user has answered, including when they kept nothing, run `sieve.py commit "<run>"` so the same conversations are not proposed again. Only skip this if the user stopped before reviewing.

## Background output

```json
{
  "conversations": [{"id": "...", "date": "...", "summary": "..."}],
  "proposals": [
    {"kind": "rule", "text": "...", "why": "...", "evidence": "...", "conversation": "...", "date": "...", "edits": "existing item text, or null"}
  ],
  "personal": [{"text": "...", "evidence": "..."}]
}
```
