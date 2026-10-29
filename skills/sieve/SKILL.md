---
name: sieve
description: Read this project's past Claude Code conversations that have not been read yet, log a one-line summary of each, and write the few rules and insights worth sharing to the repo's sieve-learnings skill. Run with /sieve; /sieve --attach to do it automatically at every session start, /sieve --detach to stop.
argument-hint: "[--attach | --detach | --status | --here]"
disable-model-invocation: true
---

# Sieve

Turn what people and Claude learned in past conversations about this repository into a short, shared table of learnings that every teammate's Claude reads, plus a log of what each conversation was about. It works in three layers: a cheap model extracts candidates, a strong model compares them with what the table already says, and a script applies the result. Bring little, and only what is high quality.

Work without asking the user anything. The user reviews the result in the git diff. Talk to the user in the language they use with you.

The script used below is `python3 "${CLAUDE_PLUGIN_ROOT}/skills/sieve/scripts/sieve.py"`, called `sieve.py` here.

## Pick the mode from the arguments: `$ARGUMENTS`

- No arguments: run `sieve.py start --cwd "$PWD"` and nothing else. If it printed `"started": true`, reply with one sentence: Sieve is reading the conversations in the background and a notification will say what changed when it finishes. If it was already running, say so in one sentence. Do not read files, launch agents or do any of the steps below.
- `--attach`: run `sieve.py attach --cwd "$PWD"`. Tell the user in one sentence that from now on Sieve reads new conversations in the background whenever they open Claude Code in this repository, and a single line in the terminal says when it changes something. Stop.
- `--detach`: run `sieve.py detach --cwd "$PWD"`, confirm in one sentence, stop.
- `--status`: run `sieve.py status --cwd "$PWD"` and answer in one sentence. Stop.
- `--background <run dir>`: you are the separate process the script started, with no person watching. The script already did step 1. Do steps 2 to 4 for that run dir (its batches are the `batch-*.md` files in it, and its context is `context.json`), print ONLY the JSON object from step 4, and stop. Do not write files.
- `--here`: run every step below in this conversation, for debugging.

## 1. Scan

Run `sieve.py scan --cwd "$PWD"`. It prints a JSON manifest: `repo`, `is_git_repo`, `learnings`, `context`, `conversations_log`, `run`, `conversations`, `batches` (markdown files holding only what people and Claude wrote; tool output is already stripped).

If `conversations` is 0, run `sieve.py commit "<run>"`, tell the user in one sentence there is nothing new since the last run, and stop.

## 2. Extract (Haiku)

Launch one `sieve:reader` agent per batch, all in a single message so they run in parallel. Prompt each with just the absolute path of its batch file. If that agent type is unavailable, use `general-purpose` with `model: "haiku"` and paste the contents of `${CLAUDE_PLUGIN_ROOT}/agents/reader.md` (without its frontmatter) above the path.

Each returns `{"conversations": [...], "candidates": [...]}`. Collect all conversations and all candidates. Do not filter or rewrite the candidates yourself.

## 3. Compare (Opus)

If there are no candidates, skip to step 4 with no ops.

Launch one `sieve:judge` agent. Its prompt: the absolute path of `<run>/context.json` (the current learnings table and the repo docs), then the line `Candidates:` followed by the collected candidates as a JSON array. If that agent type is unavailable, use `general-purpose` with `model: "opus"` and paste the contents of `${CLAUDE_PLUGIN_ROOT}/agents/judge.md` (without its frontmatter) above it.

It returns `{"ops": [...], "dropped": [...]}`: each op adds a row, updates an existing row (new wording, or only more supporting conversations), or removes a row that turned out wrong. Use its ops as they are.

## 4. Update

Build this object:

```json
{
  "conversations": [{"id": "8-char id", "date": "YYYY-MM-DD", "summary": "One sentence."}],
  "ops": ["the judge's ops, unchanged"],
  "dropped": ["the judge's dropped list, unchanged"]
}
```

`conversations` holds every conversation the readers summarized. In background mode, print ONLY this object and stop. Otherwise write it to `<run>/result.json` and run `sieve.py apply "<run>"`. It applies the ops to the learnings table in `.claude/skills/sieve-learnings/SKILL.md`, records the conversations in `.claude/sieve/conversations.csv`, and marks them as read. It prints how many rows were added, updated and removed.

## 5. Report

One or two sentences: how many learnings were added, updated and removed (name them in a few words each if there are three or fewer changes) and how many conversations were logged, and that the changes are in `.claude/skills/sieve-learnings/` and `.claude/sieve/conversations.csv` for them to review in the diff and commit. Do not list dropped candidates.
