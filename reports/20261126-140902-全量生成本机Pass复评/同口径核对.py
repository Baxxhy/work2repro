"""Run with the pinned Req2Test environment after copying all eight local score files."""
import csv
import json
from pathlib import Path
from req2test.aggregate import aggregate
from req2test.report import population_exclusions

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "预测快照"

def indexed(paths):
    rows = {}
    for path in paths:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            assert row["instance_id"] not in rows, row["instance_id"]
            rows[row["instance_id"]] = row
    return rows

predictions = indexed([SNAPSHOT / "predictions.jsonl"])
remote = indexed([SNAPSHOT / "final-instances.jsonl"])
local = indexed(sorted((ROOT / "本机评分").glob("*/instances.jsonl")))
assert len(predictions) == 2051 and predictions.keys() == remote.keys() == local.keys()
excluded = population_exclusions("1.1")["excluded"]
prior = json.loads((SNAPSHOT / "final-pass-at-1.json").read_text())
assert excluded == prior["population_exclusions"]
metrics = {}
for label, runs in [("remote", remote), ("local", local)]:
    scores = aggregate(list(runs.values()), excluded=excluded)
    cells = scores["cells"]
    assert len(cells) == 8 and all(cell["complete"] for cell in cells.values())
    den = sum(cell["n"] - cell["excluded"] for cell in cells.values())
    passed = sum(cell["passes"] for cell in cells.values())
    metrics[label] = dict(official_macro=scores["mean"]["th"]["pass_at_1"]["value"],
                          denominator=den, passes=passed, pooled=passed / den, projects=cells)
assert abs(metrics["remote"]["official_macro"]-prior["official_macro"]["value"]) < 1e-12
with (ROOT / "逐任务结果对照.tsv").open("w") as out:
    writer=csv.writer(out,delimiter="\t")
    writer.writerow(["instance_id","remote_passed","local_passed","remote_outcome","local_outcome","remote_exclusion","local_exclusion","protocol_exclusion"])
    for key in sorted(local):
        a,b=remote[key],local[key]
        assert a["project"]==b["project"]==key.split("/")[0] and a["view"]==b["view"]=="th"
        writer.writerow([key,a["passed"],b["passed"],a["engine_outcome"],b["engine_outcome"],a["exclusion"],b["exclusion"],excluded.get(key)])
(ROOT/"全量同口径汇总.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+"\n")
