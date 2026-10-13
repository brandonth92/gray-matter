#!/usr/bin/env python3
"""Find dated, person-related evidence in local markdown sources."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:_|$)")


def source_files(path):
    path = Path(path)
    if path.is_file():
        return [path] if path.suffix.lower() == ".md" else []
    return sorted(p for p in path.rglob("*.md") if p.is_file())


def aliases_for(person):
    stem = person.stem
    words = [w for w in re.split(r"[-_\s]+", stem) if w]
    aliases = {stem, stem.replace("-", " "), stem.replace("_", " ")}
    if words:
        aliases.add(words[0])
        aliases.add(" ".join(words))
    if len(words) > 1:
        aliases.add(words[-1])
        aliases.add(f"{words[0]} {words[-1]}")
        aliases.add(f"{words[-1]} {words[0]}")
    # Obsidian aliases are commonly declared as `aliases: ["..."]` or bullets.
    try:
        text = person.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for value in re.findall(r"(?:aliases?|aka)\s*:\s*(.*)", text, re.I):
        aliases.update(x.strip(" '\"[],-") for x in re.split(r",|\||;", value) if x.strip(" '\"[],-"))
    return sorted((a for a in aliases if len(a) >= 2), key=len, reverse=True)


def state_pairs():
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    pairs = set()
    for item in data.get("processed", []):
        if isinstance(item, dict):
            pairs.add((item.get("source_hash"), item.get("person_file")))
    return pairs


def compact_summary(line):
    value = re.sub(r"[`*_#>]", "", line)
    value = re.sub(r"\s+", " ", value).strip(" -\t")
    if len(value) > 160:
        return value[:159].rstrip() + "…"
    return value


def extract(args):
    people = sorted(Path(args.people_dir).glob("*.md"))
    identities = [(p, aliases_for(p)) for p in people]
    seen = state_pairs()
    candidates = []
    for source in source_files(args.sources):
        match = DATE_RE.match(source.name)
        if not match:
            continue
        date = match.group(1)
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        for person, aliases in identities:
            if (digest, person.name) in seen:
                continue
            found = None
            for number, line in enumerate(lines, 1):
                if any(re.search(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", line, re.I) for alias in aliases):
                    found = (number, line)
                    break
            if found is None:
                continue
            candidates.append({
                "person_file": person.name,
                "date": date,
                "summary_draft": compact_summary(found[1]),
                "source_path": str(source.resolve()),
                "source_type": "transcript" if "transcript" in str(source).lower() else "markdown",
                "evidence_line": found[0],
                "evidence_text": found[1],
            })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", required=True)
    parser.add_argument("--people-dir", default="/home/eden/Documents/Eden Knowledge Base/People")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    extract(args)


if __name__ == "__main__":
    main()
