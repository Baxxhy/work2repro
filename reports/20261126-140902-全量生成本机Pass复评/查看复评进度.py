"""Run in the KVM guest. Read scoring journals without changing worker state."""
import collections
import json
from pathlib import Path

home = Path.home()
inputs = home / "reeval/medium-th-2051-20261126-140902/input"
prefix = "medium-local-exec-20261126-140902-"
for src in sorted(inputs.glob("*.jsonl")):
    project = src.stem
    score = home / ".req2test/runs" / (prefix + project) / project / "th"
    done = set()
    outcomes = collections.Counter()
    files = sorted((score / "exec/raw").glob("*.jsonl"))
    if (score / "instances.jsonl").exists():
        files = [score / "instances.jsonl"]
    for path in files:
        for line in path.read_bytes().splitlines(keepends=True):
            if not line.endswith(b"\n"):
                continue
            row = json.loads(line)
            iid = row.get("instance_id") or row.get("item_id")
            if iid and iid not in done:
                done.add(iid)
                outcomes[row.get("engine_outcome") or row.get("outcome")] += 1
    print(project, len(done), sum(1 for _ in src.open()), dict(outcomes))
