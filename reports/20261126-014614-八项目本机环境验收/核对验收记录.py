import json
from pathlib import Path

PROJECTS = {
    "algorand-sdk": 111, "coddy-agent": 274, "coreshop": 334,
    "e-petitions": 98, "kapua": 330, "prestashop": 348,
    "python-docx": 237, "sylius": 319,
}
root = Path(__file__).resolve().parent
rows = []
for project, total in PROJECTS.items():
    directory = root / "证据" / project
    def load(name):
        return json.loads((directory / name).read_text())
    probe = load("preflight.json")
    result = load("validate.json")
    subset = load("subset.json")
    assert probe["project"] == result["project"] == project
    assert probe["ok"] and result["ok"] and all(result["checks"].values())
    assert result["n"] == result["pass"] == len(result["instances"]) == 1
    assert subset["projects"][project] == {"n": 1, "of": total}
    pairs = result["pairs"]
    observed = [json.loads(line) for line in (directory / "变异记录.jsonl").read_text().splitlines()]
    assert all(row["instance_id"] == result["instances"][0] for row in observed)
    assert len({r["mutant_id"] for r in observed}) == len(observed) == pairs["g_pairs_with_rows"]
    assert pairs["killed"] + pairs["survived"] + pairs["dropped"] == len(observed)
    rows.append([project, total, result["instances"][0], pairs["g_pairs"], pairs["killed"], pairs["survived"], pairs["dropped"], result["api_f1_mean"], result["coverage_j_mean"]])
assert sum(PROJECTS.values()) == 2051
for row in rows:
    print(*row, sep="\t")
