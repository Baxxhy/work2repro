"""Read this run's checkpoint and print a shareable status snapshot on 4x3090."""

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo


BASE = Path("/root/Baxxhy/work2/reproductions/req2test")
RUN = BASE / "req2test-medium-full-20261123"
AUDIT = Path("/root/Baxxhy/work2/diagnostics/20261124-190146-Req2Test额度复查与续跑/remote")
RESET = 1795509013
TZ = ZoneInfo("Asia/Shanghai")


def stamp(value):
    return datetime.fromtimestamp(value, TZ).isoformat(timespec="seconds")


def load(path):
    return json.loads(path.read_text())


def main():
    state = load(RUN / "state.json")
    original = load(AUDIT / "finished-before.json")
    progress = load(RUN / "progress.json")
    checks = [c for c in state.get("quota_window_checks", []) if c["reset_at"] == RESET]
    available = [c for c in checks if c["status"] == "available"]
    after = available[-1]["checked_at"] if available else None
    current = state["tasks"]
    assert len({t["id"] for t in current.values()}) == len(current) == 2051
    previous_unchanged = all(current[k]["gen"] == "finished" and
                             [current[k]["gen_attempts"], current[k]["prediction"]] == row[:2]
                             for k, row in original.items())
    assert previous_unchanged
    checked_hashes = None
    if "--check-hashes" in sys.argv:
        for attempts, path, expected in original.values():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
        checked_hashes = len(original)
    jobs = [j for j in state["jobs"].values() if after and j["start"] >= after and j["phase"] == "gen_req"]
    successful = [j for j in jobs if j.get("generation_outcome", {}).get("reason") == "normal_completion"
                  and j["generation_outcome"].get("prediction_valid")]
    finished = [j["end"] for j in state["jobs"].values()
                if j.get("generation_outcome", {}).get("reason") == "normal_completion"]
    net_ids = {t["id"] for t in current.values() if t["gen"] == "infra_blocked" and
               t.get("reason") == "network_interruption"}
    recovery = set(load(BASE / "req2test-medium-network260-1123/recovery-ids.json"))
    service = subprocess.check_output(["systemctl", "show", RUN.name + ".service", "-p", "InvocationID",
                                       "-p", "ActiveState", "-p", "SubState", "-p", "MainPID"],
                                      text=True).strip().splitlines()
    output = dict(time=stamp(datetime.now().timestamp()), state_time=stamp((RUN / "state.json").stat().st_mtime),
                  service=dict(row.split("=", 1) for row in service), total=len(current),
                  generation=dict(Counter(t["gen"] for t in current.values())),
                  evaluations=dict(Counter(t["evaluation"] for t in current.values())),
                  evaluation_rows=progress["observed_execution_rows"], evaluation_groups=list(state["groups"]),
                  generation_cap=state["generation_cap"], previous_completion_count=len(original),
                  previous_attempts_and_paths_unchanged=previous_unchanged, verified_hashes=checked_hashes,
                  block_kind=(state.get("block") or {}).get("kind"), check_history=checks,
                  last_normal_completion=stamp(max(finished)) if finished else None,
                  post_resume_launched=len(jobs), post_resume_valid=len(successful),
                  redispatched_previous_completions=sum(j["key"] in original for j in jobs),
                  network_blocked=len(net_ids), already_in_frozen_recovery=len(net_ids & recovery),
                  outside_frozen_recovery=len(net_ids - recovery))
    if successful:
        example=max(successful,key=lambda j:j["end"])
        output["completed_example"] = dict(task=example["key"], completed=stamp(example["end"]))
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
