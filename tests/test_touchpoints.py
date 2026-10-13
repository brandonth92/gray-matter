import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import extract
import apply as ap


def setup(tmp_path, monkeypatch):
    people = tmp_path / "People"
    people.mkdir()
    (people / "Brian-Hatcher.md").write_text("# Brian\n", encoding="utf-8")
    sources = tmp_path / "sources"
    sources.mkdir()
    source = sources / "2026-09-18_abc123_chat.md"
    source.write_text("Brian Hatcher reviewed the contact record.\n", encoding="utf-8")
    monkeypatch.setattr(extract, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(ap, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(ap, "VAULT", tmp_path / "vault")
    return people, source


def candidate(source, person="Brian-Hatcher.md", summary="Reviewed the contact record"):
    return {"person_file": person, "date": "2026-09-18", "summary_draft": summary,
            "source_path": str(source), "source_type": "transcript", "evidence_line": 1,
            "evidence_text": summary}


def test_extract_date_resolution_and_idempotency(tmp_path, monkeypatch):
    people, source = setup(tmp_path, monkeypatch)
    out = tmp_path / "candidates.json"
    args = argparse.Namespace(sources=str(source.parent), people_dir=str(people), out=str(out))
    first = extract.extract(args)
    assert first[0]["date"] == "2026-09-18"
    assert first[0]["person_file"] == "Brian-Hatcher.md"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    ap.STATE.write_text(json.dumps({"processed": [{"source_hash": digest, "person_file": "Brian-Hatcher.md"}]}))
    assert extract.extract(args) == []


def test_append_only_wikilink_receipt_and_dedupe(tmp_path, monkeypatch, capsys):
    people, source = setup(tmp_path, monkeypatch)
    vault = tmp_path / "vault"
    (vault / "Notes").mkdir(parents=True)
    vault_source = vault / "Notes" / source.name
    vault_source.write_bytes(source.read_bytes())
    ap.VAULT = vault
    old = (people / "Brian-Hatcher.md").read_bytes()
    result = ap.append_one(candidate(vault_source), people, {"processed": []}, False)
    new = (people / "Brian-Hatcher.md").read_bytes()
    assert new.startswith(old)
    assert "[[Notes/2026-09-18_abc123_chat|Transcript 2026-09-18]]" in new.decode()
    assert len(result["block"]) == len(new) - len(old)
    state = {"processed": []}
    ap.append_one(candidate(vault_source), people, state, False)
    before = (people / "Brian-Hatcher.md").read_bytes()
    assert ap.append_one(candidate(vault_source), people, state, False) is None
    assert (people / "Brian-Hatcher.md").read_bytes() == before


def test_guards_dry_run_and_cli_receipt(tmp_path, monkeypatch):
    people, source = setup(tmp_path, monkeypatch)
    before = (people / "Brian-Hatcher.md").read_bytes()
    state = {"processed": []}
    assert ap.append_one(candidate(source), people, state, True)
    assert (people / "Brian-Hatcher.md").read_bytes() == before
    import pytest
    with pytest.raises(ValueError):
        ap.append_one(candidate(source, summary="DRAFT: fill this in"), people, state, True)
    with pytest.raises(ValueError):
        ap.append_one(candidate(source, person="../escape.md"), people, state, True)


def test_cli_receipt_and_failure_exit(tmp_path, monkeypatch):
    people, source = setup(tmp_path, monkeypatch)
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps([candidate(source)]))
    script = Path(ap.__file__)
    live_state = tmp_path / "cli-state.json"
    ok = subprocess.run([sys.executable, str(script), "--candidates", str(candidates), "--people-dir", str(people), "--state", str(live_state)], capture_output=True, text=True)
    assert ok.returncode == 0 and "bytes_appended=" in ok.stdout
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([candidate(source, summary="draft")]))
    failed = subprocess.run([sys.executable, str(script), "--candidates", str(bad), "--people-dir", str(people), "--state", str(live_state)], capture_output=True, text=True)
    assert failed.returncode != 0
    # Failed batch must not silently overwrite or lose persisted state from the earlier success.
    assert json.loads(live_state.read_text())["processed"], "failed run must preserve prior persisted appends"
