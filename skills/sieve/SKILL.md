---
name: sieve
description: Read this project's past Claude Code conversations that have not been read yet, log a one-line summary of each, and write the few rules and insights worth sharing to the repo's sieve-learnings skill. Run with /sieve; /sieve --attach to do it automatically at every session start, /sieve --detach to stop.
argument-hint: "[--attach | --detach | --status]"
disable-model-invocation: true
---

# Sieve

Turn what people and Claude learned in past conversations about this repository into a short, shared skill that every teammate's Claude reads, plus a log of what each conversation was about. Bring little, and only what is high quality.

Work without asking the user anything. The user reviews the result in the git diff, not in this conversation. Talk to the user in the language they use with you.

The script used below is `python3 "${CLAUDE_PLUGIN_ROOT}/skills/sieve/scripts/sieve.py"`, called `sieve.py` here.

## Pick the mode from the arguments: `$ARGUMENTS`

- `--attach`: run `sieve.py attach --cwd "$PWD"`. Tell the user in one sentence that from now on Sieve reads new conversations in the background whenever they open Claude Code in this repository, and a single line in the terminal says when it adds something. Stop.
- `--detach`: run `sieve.py detach --cwd "$PWD"`, confirm in one sentence, stop.
- `--status`: run `sieve.py status --cwd "$PWD"` and answer in one sentence. Stop.
- `--background <run dir>`: you were started by the hook with no person present. Do steps 2 and 3 for that run dir (its batches are the `batch-*.md` files in it; the learnings and log are `<repo>/.claude/skills/sieve-learnings/SKILL.md` and `conversations.md`). Then print ONLY the JSON object from step 4 and stop. Do not write files.
- No arguments: steps 1 to 5 below.

## 1. Scan

Run `sieve.py scan --cwd "$PWD"`. It prints a JSON manifest: `repo`, `is_git_repo`, `learnings`, `conversations_log`, `run`, `conversations`, `batches` (markdown files holding only what people and Claude wrote; tool output is already stripped).

If `is_git_repo` is false and exactly one folder directly inside `$PWD` is a git repository, scan again with `--cwd` set to that repository and use that manifest instead.

If `conversations` is 0, run `sieve.py commit "<run>"`, tell the user in one sentence there is nothing new since the last run, and stop.

## 2. Read the batches

Launch one `sieve:reader` agent per batch, all in a single message so they run in parallel. Prompt each with just the absolute path of its batch file. If that agent type is unavailable, use `general-purpose` with `model: "haiku"` and paste the contents of `${CLAUDE_PLUGIN_ROOT}/agents/reader.md` (without its frontmatter) above the path.

Each returns `{"conversations": [...], "candidates": [...]}`. Collect them all.

## 3. Select

This is the step that decides quality. Do it yourself, carefully. Readers are generous; you are not.

1. Read the current learnings file and conversations log if they exist, and the repo's `CLAUDE.md` / `AGENTS.md` if they exist.
2. Drop candidates already covered there. If a candidate sharpens or contradicts an existing item, make it an edit of that item instead of a new one.
3. Merge candidates that say the same thing from different conversations. Repetition across conversations is the strongest signal that something matters.
4. Drop every candidate that fails either test: it applies to future tasks beyond the one it came from, and a teammate starting a new conversation on this repo would make a mistake or waste a round without it. Decisions about one screen or feature fail the first test unless they state a principle that covers others. Facts that have already gone stale fail too.
5. Rewrite each survivor as the general rule its evidence supports, in one or two plain sentences, with the reason when there is one. Write items in the language the repo's documentation uses; if unclear, English.
6. Drop `personal` candidates. They do not go in the repo.

There is no quota. How many survive depends on the conversations, and zero is a normal result.

## 4. Write

Write this JSON to `<run>/proposals.json` (in background mode, print it instead):

```json
{
  "conversations": [{"id": "8-char id", "date": "YYYY-MM-DD", "summary": "One sentence."}],
  "proposals": [
    {"kind": "rule or insight", "text": "...", "why": "the reason, or empty", "date": "YYYY-MM-DD", "edits": "an existing item's text this replaces, or null"}
  ]
}
```

`conversations` holds every conversation the readers summarized; one that already has a row in the log gets a summary covering both its old and new parts. Then run `sieve.py apply "<run>"`. It writes the learnings and the log into `.claude/skills/sieve-learnings/` and marks the conversations as read.

## 5. Report

One or two sentences: how many learnings were added (name them in a few words each if there are three or fewer) and how many conversations were logged, and that the changes are in `.claude/skills/sieve-learnings/` for them to review in the diff and commit. Do not list items, quotes or anything that was dropped.
