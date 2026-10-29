#!/usr/bin/env python3
"""Condense a project's Claude Code conversations into reviewable batches.

Claude Code stores every conversation as a .jsonl file under
~/.claude/projects/<encoded cwd>/. Almost all of that weight is tool output
(file reads, logs, screenshots). This script keeps only what people and
Claude wrote to each other, remembers how far it has read in every
conversation, and writes the new part as markdown batches.

  sieve.py scan    [--cwd PATH]     write batches for unread text, print manifest
  sieve.py apply   RUN_DIR          write a run's result.json to the repo, mark it read
  sieve.py commit  RUN_DIR          mark a run's text as read without writing
  sieve.py status  [--cwd PATH]     what is pending or attached
  sieve.py attach  [--cwd PATH]     read new conversations at every session start
  sieve.py detach  [--cwd PATH]
  sieve.py hook                     SessionStart hook (reads the hook JSON on stdin)
  sieve.py background --cwd PATH    scan and write without a person, used by the hook
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
PROJECTS = HOME / "projects"
SIEVE_HOME = HOME / "sieve"
SCRIPT = Path(__file__).resolve()

USER_LIMIT = 3000
CLAUDE_LIMIT = 2000
DEFAULT_BATCH_CHARS = 120_000
IMAGE_LINE = re.compile(r"^\[Image[^\]]*\]\s*$", re.M)


def encode(path):
    # Claude Code names a project's folder after its absolute path, with every
    # character outside [A-Za-z0-9-] replaced by "-".
    return re.sub(r"[^A-Za-z0-9-]", "-", path)


def repo_root(cwd):
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return cwd


def folder_cwd(folder):
    """The directory a project folder's conversations were started in."""
    for f in folder.glob("*.jsonl"):
        with f.open(errors="replace") as fh:
            for _, line in zip(range(50), fh):
                m = re.search(r'"cwd":"((?:[^"\\]|\\.)*)"', line)
                if m:
                    return json.loads('"' + m.group(1) + '"')
    return None


def transcripts(root):
    """Conversations about `root`.

    Every conversation started in the repo or below it (subfolders,
    worktrees) counts. A conversation started in a folder above the repo
    counts only if it touched the repo, which shows up as the repo's path
    somewhere in the transcript.
    """
    if not PROJECTS.is_dir():
        return
    home = str(Path.home())
    needle = root.encode()
    for d in sorted(PROJECTS.iterdir()):
        if not d.is_dir():
            continue
        cwd = folder_cwd(d)
        if not cwd:
            continue
        if cwd == root or cwd.startswith(root + "/"):
            yield from d.glob("*.jsonl")
        elif root.startswith(cwd + "/") and cwd != home:
            for f in d.glob("*.jsonl"):
                with f.open("rb") as fh:
                    if needle in fh.read():
                        yield f


def state_path(root):
    return SIEVE_HOME / "state" / (encode(root) + ".json")


def load_state(root):
    p = state_path(root)
    if p.exists():
        return json.loads(p.read_text())
    return {"root": root, "sessions": {}}


def save_state(root, state):
    p = state_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1))


def is_unread(path, state):
    done = state["sessions"].get(path.stem, {})
    return path.stat().st_size != done.get("bytes", -1)


def truncate(text, limit):
    text = IMAGE_LINE.sub("", text).strip()
    if len(text) > limit:
        return text[:limit].rstrip() + " […]"
    return text


def user_text(record):
    content = record.get("message", {}).get("content")
    if isinstance(content, str):
        parts = [content]
    elif isinstance(content, list):
        parts = [b.get("text", "") for b in content if b.get("type") == "text"]
    else:
        return ""
    # Tags mark harness traffic: slash command plumbing, task notifications,
    # system reminders, command output. None of it was typed by a person.
    parts = [p for p in parts if p.strip() and not p.lstrip().startswith("<")]
    return "\n\n".join(parts)


def claude_text(record):
    content = record.get("message", {}).get("content")
    if not isinstance(content, list):
        return ""
    return "\n\n".join(b.get("text", "") for b in content if b.get("type") == "text").strip()


def invokes_sieve(record):
    content = record.get("message", {}).get("content")
    text = content if isinstance(content, str) else json.dumps(content or "")
    return bool(re.search(r"<command-name>/?(sieve:)?sieve</command-name>", text))


def condense(path, start):
    """Return (turns, line_count, meta) for lines after `start`."""
    lines = path.read_text(errors="replace").splitlines()
    if start > len(lines):  # file was rewritten; read it again
        start = 0
    turns, meta = [], {}
    for raw in lines[start:]:
        try:
            r = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = r.get("type")
        if kind not in ("user", "assistant"):
            continue
        if r.get("entrypoint", "").startswith("sdk"):
            # Conversations an app or a script opened through the SDK or
            # `claude -p` are product traffic, not people working on the repo.
            continue
        if r.get("isSidechain") or r.get("isMeta"):
            continue
        meta.setdefault("date", (r.get("timestamp") or "")[:10])
        meta.setdefault("branch", r.get("gitBranch") or "")
        if kind == "user":
            if invokes_sieve(r):
                # The rest of this conversation is sieve reviewing itself.
                break
            text = truncate(user_text(r), USER_LIMIT)
            if text:
                turns.append(("User", text))
        else:
            text = truncate(claude_text(r), CLAUDE_LIMIT)
            if text:
                turns.append(("Claude", text))
    return turns, len(lines), meta


def scan(root, batch_chars=DEFAULT_BATCH_CHARS, exclude=()):
    state = load_state(root)
    run_dir = SIEVE_HOME / "runs" / encode(root) / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    cursors, blocks, ids = {}, [], []
    for f in sorted(transcripts(root), key=lambda p: p.stat().st_mtime):
        sid = f.stem
        if sid in exclude or not is_unread(f, state):
            continue
        size = f.stat().st_size
        start = state["sessions"].get(sid, {}).get("lines", 0)
        turns, total, meta = condense(f, start)
        cursors[sid] = {"lines": total, "bytes": size}
        if not any(who == "User" for who, _ in turns):
            continue
        head = f"## Conversation {sid[:8]} · {meta.get('date', '')}"
        if meta.get("branch"):
            head += f" · branch {meta['branch']}"
        if start:
            head += " · continued (earlier part already read)"
        body = "\n\n".join(f"**{who}:** {text}" for who, text in turns)
        blocks.append(head + "\n\n" + body + "\n")
        ids.append(sid[:8])

    batches, current = [], ""
    for block in blocks:
        if current and len(current) + len(block) > batch_chars:
            batches.append(current)
            current = ""
        current += block + "\n"
    if current:
        batches.append(current)

    paths = []
    for i, text in enumerate(batches, 1):
        p = run_dir / f"batch-{i:03d}.md"
        p.write_text(text)
        paths.append(str(p))
    (run_dir / "cursors.json").write_text(json.dumps({"root": root, "sessions": cursors}))
    write_context(run_dir, root)

    skill_dir = Path(root) / ".claude" / "skills" / "sieve-learnings"
    return {
        "repo": root,
        "is_git_repo": (Path(root) / ".git").exists(),
        "learnings": str(skill_dir / "SKILL.md"),
        "context": str(run_dir / "context.json"),
        "conversations_log": str(skill_dir / "conversations.md"),
        "run": str(run_dir),
        "conversations": len(blocks),
        "conversation_ids": ids,
        "chars": sum(len(b) for b in batches),
        "batches": paths,
    }


def commit(run_dir):
    pending = json.loads((run_dir / "cursors.json").read_text())
    root = pending["root"]
    state = load_state(root)
    state["sessions"].update(pending["sessions"])
    state["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_state(root, state)
    return len(pending["sessions"])


LEARNINGS_HEADER = """---
name: sieve-learnings
description: Rules and lessons learned by people working on this repository with Claude, collected by Sieve. Read at the start of any task in this repository, before planning or writing code. conversations.md in the same folder logs what past conversations worked on.
---

# Learnings

Rules and insights from past Claude Code conversations about this repository, kept by Sieve. Follow the rules; use the insights. Conversations are listed by id in conversations.md.
"""

COLUMNS = ["ID", "Type", "Learning", "Why", "Conversations", "Added", "Updated"]

LOG_HEADER = """# Conversations

One line per Claude Code conversation about this repository, newest first. Written by Sieve.

| Date | Conversation | Who | Summary |
|---|---|---|---|
"""

CELL_SPLIT = re.compile(r"(?<!\\)\|")


def cell(text):
    return (text or "").replace("\n", " ").replace("|", "\\|").strip()


def uncell(text):
    return text.replace("\\|", "|").strip()


def read_learnings(path):
    """The learnings table as a list of dicts, plus the text above it."""
    if not path.exists():
        return LEARNINGS_HEADER, []
    text = path.read_text()
    rows, head = [], []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| ID |"):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            cells = [uncell(c) for c in CELL_SPLIT.split(line.strip())[1:-1]]
            row = dict(zip(["id", "type", "learning", "why", "conversations", "added", "updated"], cells))
            row["conversations"] = [c.strip() for c in row.get("conversations", "").split(",") if c.strip()]
            rows.append(row)
            continue
        in_table = False
        head.append(line)
    if not rows:
        # Files written before the table format: "- text (date)" under ## Rules / ## Insights.
        kind, head = None, []
        for line in text.splitlines():
            if line.startswith("## "):
                kind = "insight" if "insight" in line.lower() else "rule"
                continue
            m = re.match(r"^- (.*?)(?: \((\d{4}-\d{2}-\d{2})\))?$", line)
            if kind and m:
                rows.append(new_row(kind, m.group(1), "", [], m.group(2) or ""))
            elif not kind:
                head.append(line)
    return "\n".join(head).rstrip() + "\n", rows


def new_row(kind, learning, why, conversations, date):
    rid = hashlib.sha1(learning.encode()).hexdigest()[:6]
    return {"id": rid, "type": kind, "learning": learning, "why": why,
            "conversations": conversations, "added": date, "updated": date}


def write_table(path, head, rows):
    order = {"rule": 0, "insight": 1}
    rows = sorted(rows, key=lambda r: (order.get(r["type"], 2), r["added"], r["id"]))
    lines = [head.rstrip(), "",
             "| " + " | ".join(COLUMNS) + " |",
             "|" + "---|" * len(COLUMNS)]
    for r in rows:
        lines.append("| " + " | ".join(cell(x) for x in [
            r["id"], r["type"], r["learning"], r["why"],
            ", ".join(r["conversations"]), r["added"], r["updated"]]) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def apply_ops(path, ops):
    """Apply the judge's add/update/remove operations. Returns counts."""
    head, rows = read_learnings(path)
    by_id = {r["id"]: r for r in rows}
    today = time.strftime("%Y-%m-%d")
    done = {"added": 0, "updated": 0, "removed": 0}
    for op in ops:
        kind = op.get("op")
        if kind == "add" and op.get("learning"):
            row = new_row(op.get("type", "rule"), op["learning"].strip(), (op.get("why") or "").strip(),
                          list(op.get("conversations") or []), op.get("date") or today)
            while row["id"] in by_id:
                row["id"] = hashlib.sha1(row["id"].encode()).hexdigest()[:6]
            by_id[row["id"]] = row
            done["added"] += 1
        elif kind == "update" and op.get("id") in by_id:
            row = by_id[op["id"]]
            if op.get("learning"):
                row["learning"] = op["learning"].strip()
            if op.get("why") is not None and "why" in op:
                row["why"] = (op.get("why") or "").strip()
            for c in op.get("add_conversations") or []:
                if c not in row["conversations"]:
                    row["conversations"].append(c)
            row["updated"] = op.get("date") or today
            done["updated"] += 1
        elif kind == "remove" and op.get("id") in by_id:
            del by_id[op["id"]]
            done["removed"] += 1
    write_table(path, head, list(by_id.values()))
    return done


def git_user(root):
    try:
        out = subprocess.run(["git", "-C", root, "config", "user.name"],
                             capture_output=True, text=True)
        return out.stdout.strip() or os.environ.get("USER", "")
    except FileNotFoundError:
        return os.environ.get("USER", "")


def write_log(path, conversations, who):
    lines = (path.read_text() if path.exists() else LOG_HEADER).splitlines()
    head = next(i for i, l in enumerate(lines) if l.startswith("|---")) + 1
    for c in sorted(conversations, key=lambda c: c.get("date", "")):
        row = f"| {c.get('date', '')} | {c['id']} | {who} | {cell(c.get('summary', ''))} |"
        hit = next((i for i, l in enumerate(lines) if l.startswith("| ") and f"| {c['id']} |" in l), None)
        if hit is not None:
            lines[hit] = row
        else:
            lines.insert(head, row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n")
    return len(conversations)


def write_context(run_dir, root):
    """What the judge compares candidates against: the current table and the docs."""
    folder = Path(root) / ".claude" / "skills" / "sieve-learnings"
    _, rows = read_learnings(folder / "SKILL.md")
    docs = {}
    for name in ("CLAUDE.md", "AGENTS.md", ".claude/CLAUDE.md"):
        p = Path(root) / name
        if p.exists():
            docs[name] = p.read_text()[:20000]
    (run_dir / "context.json").write_text(json.dumps({"learnings": rows, "docs": docs}, indent=1))


def apply(run_dir, announce=False):
    """Write a run's result.json to the repo and mark its text as read."""
    found = json.loads((run_dir / "result.json").read_text())
    root = json.loads((run_dir / "cursors.json").read_text())["root"]
    folder = Path(root) / ".claude" / "skills" / "sieve-learnings"
    done = {"added": 0, "updated": 0, "removed": 0}
    if found.get("ops"):
        done = apply_ops(folder / "SKILL.md", found["ops"])
    logged = 0
    if found.get("conversations"):
        logged = write_log(folder / "conversations.md", found["conversations"], git_user(root))
    commit(run_dir)
    state = load_state(root)
    # Only a background run announces itself; after /sieve the person already read the report.
    state["last_applied"] = {**done, "conversations": logged, "seen": not announce}
    save_state(root, state)
    return {**done, "conversations": logged, "folder": str(folder)}


def running(state):
    pid = state.get("running")
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def cmd_scan(args):
    print(json.dumps(scan(repo_root(args.cwd), args.batch_chars), indent=2))


def cmd_apply(args):
    print(json.dumps(apply(Path(args.run_dir))))


def cmd_commit(args):
    print(json.dumps({"marked": commit(Path(args.run_dir))}))


def cmd_status(args):
    root = repo_root(args.cwd)
    state = load_state(root)
    unread = sum(1 for f in transcripts(root) if is_unread(f, state))
    print(json.dumps({
        "repo": root,
        "attached": bool(state.get("attached")),
        "last_run": state.get("last_run"),
        "conversations_read": len(state["sessions"]),
        "transcripts_with_unread_text": unread,
        "background_running": running(state),
        "last_applied": state.get("last_applied"),
    }, indent=2))


def cmd_attach(args, on=True):
    root = repo_root(args.cwd)
    state = load_state(root)
    state["attached"] = on
    save_state(root, state)
    print(json.dumps({"repo": root, "attached": on}))


def notify(text):
    # systemMessage is shown to the person in the terminal and never reaches
    # the model, so the conversation itself is left alone.
    print(json.dumps({"systemMessage": text}))


def by_a_person(path):
    """Whether a transcript holds a conversation a person had, not SDK traffic."""
    with path.open("rb") as fh:
        data = fh.read()
    return b'"entrypoint":"cli"' in data or b'"entrypoint":"claude-desktop"' in data


def cmd_hook(args):
    if os.environ.get("SIEVE_BACKGROUND"):
        return
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    root = repo_root(data.get("cwd") or os.getcwd())
    state = load_state(root)
    if not state.get("attached"):
        return

    news = []
    done = state.get("last_applied")
    if done and not done.get("seen"):
        done["seen"] = True
        save_state(root, state)
        parts = [f"{done[k]} {k}" for k in ("added", "updated", "removed") if done.get(k)]
        if parts:
            news.append(", ".join(parts) + " in .claude/skills/sieve-learnings")

    current = data.get("session_id")
    unread = [] if running(state) else [
        f for f in transcripts(root) if f.stem != current and is_unread(f, state)]
    if unread:
        log = SIEVE_HOME / "background.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(SCRIPT), "background", "--cwd", root]
        if current:
            cmd += ["--exclude", current]
        subprocess.Popen(
            cmd, cwd=root, start_new_session=True,
            stdin=subprocess.DEVNULL, stdout=log.open("a"), stderr=subprocess.STDOUT,
            env={**os.environ, "SIEVE_BACKGROUND": "1"},
        )
        people = sum(1 for f in unread if by_a_person(f))
        if people:
            news.append(f"reading {people} past conversation{'s' if people != 1 else ''} in the background")

    if news:
        notify("Sieve · " + " · ".join(news))


def extract_json(text):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def cmd_background(args):
    root = repo_root(args.cwd)
    state = load_state(root)
    if running(state):
        return
    state["running"] = os.getpid()
    save_state(root, state)
    try:
        manifest = scan(root, exclude=set(args.exclude or []))
        run = Path(manifest["run"])
        if not manifest["conversations"]:
            commit(run)  # only tool traffic or SDK sessions: nothing to propose
            return
        claude = shutil.which("claude")
        if not claude:
            print(f"{time.ctime()} Sieve: claude not on PATH")
            return
        cmd = [claude, "-p", f"/sieve:sieve --background {run}",
               "--allowedTools", "Read,Glob,Grep,Agent",
               "--add-dir", str(SIEVE_HOME),
               "--output-format", "text"]
        if os.environ.get("SIEVE_PLUGIN_DIR"):  # testing an uninstalled checkout
            cmd += ["--plugin-dir", os.environ["SIEVE_PLUGIN_DIR"]]
        out = subprocess.run(
            cmd,
            cwd=root, capture_output=True, text=True,
            env={**os.environ, "SIEVE_BACKGROUND": "1"},
        )
        found = extract_json(out.stdout)
        (run / "background-output.txt").write_text(out.stdout + out.stderr)
        if found is None:
            print(f"{time.ctime()} Sieve: no JSON from background review of {root}, see {run}")
            return
        (run / "result.json").write_text(json.dumps(found, indent=1))
        apply(run, announce=True)
    finally:
        state = load_state(root)
        if state.get("running") == os.getpid():
            state.pop("running")
            save_state(root, state)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--cwd", default=os.getcwd())
    s.add_argument("--batch-chars", type=int, default=DEFAULT_BATCH_CHARS)
    c = sub.add_parser("commit")
    c.add_argument("run_dir")
    sub.add_parser("apply").add_argument("run_dir")
    for name in ("status", "attach", "detach"):
        sub.add_parser(name).add_argument("--cwd", default=os.getcwd())
    sub.add_parser("hook")
    b = sub.add_parser("background")
    b.add_argument("--cwd", required=True)
    b.add_argument("--exclude", action="append")
    args = ap.parse_args()
    {
        "scan": cmd_scan,
        "commit": cmd_commit,
        "apply": cmd_apply,
        "status": cmd_status,
        "attach": cmd_attach,
        "detach": lambda a: cmd_attach(a, on=False),
        "hook": cmd_hook,
        "background": cmd_background,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
