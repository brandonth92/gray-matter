#!/usr/bin/env python3
"""Safely append reviewed touchpoints to canonical People notes."""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
VAULT = Path("/home/eden/Documents/Eden Knowledge Base")


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def load_state(path=None):
    state_file = Path(path) if path else STATE
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"processed": []}


def source_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_link(source):
    path = Path(source).expanduser().resolve()
    try:
        rel = path.relative_to(VAULT.resolve())
    except ValueError:
        return str(source)
    if not path.is_file():
        raise ValueError(f"wiki-link target does not exist: {path}")
    without = rel.with_suffix("").as_posix()
    stem = path.stem
    label = f"Transcript {stem.split('_', 1)[0]}" if re.match(r"\d{4}-\d{2}-\d{2}_", stem) else stem
    return f"[[{without}|{label}]]"


def target_path(people_dir, name):
    base = Path(people_dir).resolve()
    target = (base / name).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError("target is outside --people-dir")
    if target.suffix != ".md" or not target.is_file():
        raise ValueError("target People file does not exist")
    return target


def append_one(candidate, people_dir, state, dry_run):
    summary = str(candidate.get("summary_draft", "")).strip()
    if not summary or re.search(r"\bdraft\b", summary, re.I):
        raise ValueError("empty or draft-flagged summary")
    date = str(candidate.get("date", ""))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("invalid date")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("invalid date")
    if len(summary) > 160:
        raise ValueError("summary exceeds 160 characters")
    target = target_path(people_dir, candidate.get("person_file", ""))
    source = candidate.get("source_path", "")
    digest = source_hash(source)
    pair = (digest, target.name)
    processed = {(x.get("source_hash"), x.get("person_file")) for x in state.get("processed", []) if isinstance(x, dict)}
    if pair in processed:
        return None
    link = source_link(source)
    cleaned = summary.rstrip(".").rstrip() or summary
    old = target.read_bytes()
    if b"## Touchpoints" in old:
        block = (b"" if old.endswith(b"\n") else b"\n") + f"- **{date}** — {cleaned}. Source: {link}\n".encode("utf-8")
    else:
        prefix = b"" if not old else (b"" if old.endswith(b"\n") else b"\n")
        block = prefix + b"\n## Touchpoints\n\n" + f"- **{date}** — {cleaned}. Source: {link}\n".encode("utf-8")
    expected = old + block
    if dry_run:
        return {"target": target, "old": old, "expected": expected, "digest": digest, "pair": pair, "block": block}
    backup_dir = ROOT / "candidates" / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{target.name}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.bak"
    shutil.copy2(target, backup)
    before_hash = hashlib.sha256(old).digest()
    if target.stat().st_size != len(old) or hashlib.sha256(target.read_bytes()).digest() != before_hash:
        raise ValueError("target changed after snapshot")
    target.write_bytes(expected)
    actual = target.read_bytes()
    if actual != expected or actual[:len(old)] != old or actual[len(old):] != block:
        raise ValueError("byte-level append verification failed")
    state.setdefault("processed", []).append({"source_hash": digest, "person_file": target.name, "source_path": source})
    return {"target": target, "old": old, "expected": expected, "digest": digest, "pair": pair, "block": block}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--people-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--state", default=str(STATE))
    args = parser.parse_args()
    state_path = Path(args.state)
    try:
        candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
        if not isinstance(candidates, list):
            return fail("candidates file must contain a JSON list")
    except Exception as exc:
        return fail(f"invalid candidates file: {exc}")

    def persist(state):
        tmp = state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, state_path)

    try:
        state = load_state(state_path)
        saved = 0
        for candidate in candidates:
            result = append_one(candidate, args.people_dir, state, args.dry_run)
            if not result:
                continue
            if args.dry_run:
                print(f"DRY-RUN file={result['target']} would_append={len(result['block'])}")
            else:
                persist(state)
                saved += 1
                now = datetime.now(timezone.utc).isoformat()
                print(f"SUCCESS file={result['target']} bytes_appended={len(result['block'])} timestamp={now}")
        return 0
    except Exception as exc:
        return fail(f"{exc} (completed appends already persisted: {saved})")


if __name__ == "__main__":
    raise SystemExit(main())
