"""Apply a bounded status-check retry to the idle 2026-11-23 Medium queue."""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path


BASE = Path("/root/Baxxhy/work2/reproductions/req2test")
RUN = BASE / "req2test-medium-full-20261123"
UNIT = RUN.name + ".service"
AUDIT = Path("/root/Baxxhy/work2/diagnostics/20261124-190146-Req2Test额度复查与续跑/remote")
CONTROL = RUN / "control/controller.py"
BLOCK_JOB = "f473a3ee9697475c96aed6dacfaf44e5"
RESET = 1795509013

HELPER = '''def next_quota_check(reset, checks):
    attempts = [check for check in checks if check['reset_at'] == reset]
    if not attempts:
        return reset + 60
    if len(attempts) == 1:
        first = attempts[0]
        if first.get('status') == 'check_failed' and first.get('error') in ('URLError', 'TimeoutError'):
            return max(reset + 60, first['checked_at'] + 900)
    return None

'''
OLD = '''    reset=max(resets);due=reset+60
    S['quota_resume_at']=due
    checks=S.setdefault('quota_window_checks',[])
    if time.time()<due or any(x['reset_at']==reset for x in checks):return'''
NEW = '''    reset=max(resets)
    checks=S.setdefault('quota_window_checks',[])
    due=next_quota_check(reset,checks)
    S['quota_resume_at']=due
    if due is None or time.time()<due:return'''


def verify_schedule():
    namespace = {}
    exec(HELPER, namespace)
    next_check = namespace["next_quota_check"]
    base = dict(reset_at=1000, checked_at=1065)
    failed = dict(base, status="check_failed", error="URLError")
    assert next_check(1000, []) == 1060
    assert next_check(1000, [failed]) == 1965
    assert next_check(1000, [dict(failed, error="TimeoutError")]) == 1965
    assert next_check(1000, [failed, failed]) is None
    for row in [dict(failed, error="HTTPError"), dict(base, status="still_blocked"),
                dict(base, status="available"), dict(base, status="checking")]:
        assert next_check(1000, [row]) is None
    assert next_check(2000, [failed, failed]) == 2060


def read_json(path):
    return json.loads(path.read_text())


def digest(content):
    return hashlib.sha256(content).hexdigest()


def unique_replace(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError("unexpected controller version")
    return source.replace(old, new, 1)


def protect_finished(state):
    predictions = {}
    for key, task in state["tasks"].items():
        if task["gen"] == "finished":
            predictions[key] = [task["gen_attempts"], task["prediction"],
                                digest(Path(task["prediction"]).read_bytes())]
    return predictions


def main():
    verify_schedule()
    if sys.argv[1:] == ["--check"]:
        print("Quota-check schedule verified.")
        return
    if sys.argv[1:] != ["--apply"]:
        raise SystemExit("Choose --check or --apply")
    state = read_json(RUN / "state.json")
    block = state.get("block") or {}
    assert block.get("job") == BLOCK_JOB and block.get("status") == 429
    recent = [row for row in state["quota_window_checks"] if row["reset_at"] == RESET]
    assert len(recent) == 1 and recent[0]["status"] == "check_failed" and recent[0]["error"] == "URLError"
    assert time.time() >= recent[0]["checked_at"] + 900
    assert not any(j.get("state") == "running" for j in state["jobs"].values())
    assert not state["groups"] and len(state["tasks"]) == 2051
    subprocess.run(["systemctl", "is-active", "--quiet", UNIT], check=True)
    before = CONTROL.read_text()
    after = unique_replace(before, "def recover_quota_if_ready():", HELPER + "def recover_quota_if_ready():")
    after = unique_replace(after, OLD, NEW)
    after = unique_replace(after, "At most one usage check per returned window, including restarts.",
                           "Persist before I/O. A transport failure permits one delayed usage recheck.")
    compile(after, str(CONTROL), "exec")
    finished = protect_finished(state)
    assert len(finished) == 1458
    recovery = set(read_json(BASE / "req2test-medium-network260-1123/recovery-ids.json"))
    network = {t["id"] for t in state["tasks"].values() if t.get("reason") == "network_interruption"}
    AUDIT.mkdir(mode=0o700, parents=True, exist_ok=False)
    shutil.copy2(CONTROL, AUDIT / "controller-before.py")
    (AUDIT / "finished-before.json").write_text(json.dumps(finished, sort_keys=True))
    summary = dict(total=len(state["tasks"]), generation=dict(Counter(t["gen"] for t in state["tasks"].values())),
                   network=len(network), network_in_frozen_recovery=len(network & recovery),
                   network_outside_frozen_recovery=len(network - recovery),
                   before_sha256=digest(before.encode()), after_sha256=digest(after.encode()))
    (AUDIT / "before.json").write_text(json.dumps(summary))
    with tempfile.NamedTemporaryFile("w", dir=CONTROL.parent, delete=False) as tmp:
        tmp.write(after)
        tmp.flush()
        os.fsync(tmp.fileno())
        os.fchmod(tmp.fileno(), stat.S_IMODE(CONTROL.stat().st_mode))
    os.replace(tmp.name, CONTROL)
    subprocess.run(["systemctl", "restart", UNIT], check=True, timeout=45)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
