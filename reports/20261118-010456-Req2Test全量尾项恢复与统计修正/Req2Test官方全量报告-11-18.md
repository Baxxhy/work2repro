# Req2Test-Bench report: run `req2test-eval2051-resume-20261117-v1`

Benchmark version: 1.1.

**Benchmark 1.1 population.** 14 instance(s) of this run are outside it (census_pass, zero_body): they were scored into `instances.jsonl`, and no measure or disclosure below counts them; summary.json (`population`) lists them (`benchmark/config/benchmark_2.0_population.yml`).

Values are percentages, and a non-passing test counts as 0 in every column. The headline is `leaderboard` mode, the aggregation of `results/leaderboard.md`, so a run of all eight projects compares with the leaderboard. `exact` mode is printed beside it (`docs/metrics.md`).

## Mode `leaderboard` (the headline: the leaderboard's aggregation; `docs/metrics.md`)

| Project | View | N | Pass@1 | KillComplete@1 | API F1 | Coverage J | Mutation R |
|---|---|---:|---:|---:|---:|---:|---:|
| algorand-sdk | TH | 111 | 42.3 | 35.1 | 37.9 | 39.6 | 40.7 |
| coddy-agent | TH | 274 | 29.5 | 6.9 | 22.6 | 24.4 | 25.1 |
| coreshop | TH | 328 | 5.2 | 1.5 | 3.0 | 3.1 | 2.9 |
| e-petitions | TH | 98 | 30.6 | 12.2 | 0.0 | 29.8 | 29.7 |
| kapua | TH | 330 | 18.2 | 10.9 | 13.8 | 17.6 | 17.4 |
| prestashop | TH | 348 | 11.8 | 5.7 | 9.1 | 10.5 | 10.5 |
| python-docx | TH | 237 | 80.2 | 30.0 | 64.4 | 68.6 | 76.2 |
| sylius | TH | 311 | 19.9 | 4.2 | 7.0 | 15.6 | 16.0 |
| **8-project mean** | TH | | **29.7** | **13.3** | **19.7** | **26.1** | **27.3** |

## Mode `exact` (each measure over the instances it is defined for; `docs/metrics.md`)

| Project | View | N | Pass@1 | KillComplete@1 | API F1 | Coverage J | Mutation R | KillComplete@1 (strict) | KillComplete@1 (recall ≥ 0.95) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| algorand-sdk | TH | 111 | 42.3 | 35.1 | 37.9 | 39.6 | 40.7 | 35.1 | 36.9 |
| coddy-agent | TH | 274 | 29.5 | 6.9 | 22.6 | 24.4 | 25.1 | 5.8 | 16.1 |
| coreshop | TH | 328 | 5.2 | 1.5 | 3.0 | 3.1 | 2.9 | 1.5 | 1.8 |
| e-petitions | TH | 98 | 30.6 | 12.2 | 0.0 | 29.8 | 29.7 | 12.2 | 24.5 |
| kapua | TH | 330 | 18.2 | 10.9 | 13.8 | 17.6 | 17.4 | 10.9 | 14.8 |
| prestashop | TH | 348 | 11.8 | 5.7 | 9.1 | 10.5 | 10.5 | 5.7 | 6.9 |
| python-docx | TH | 237 | 80.2 | 30.0 | 64.4 | 68.6 | 76.2 | 30.0 | 57.4 |
| sylius | TH | 311 | 19.9 | 4.2 | 7.0 | 15.6 | 16.0 | 4.2 | 6.4 |
| **8-project mean** | TH | | **29.7** | **13.3** | **19.7** | **26.1** | **27.3** | **13.2** | **20.6** |

## Disclosures

- algorand-sdk/th: none
- coddy-agent/th: 2 instance(s) excluded for harness infrastructure failures; 1 instance(s) excluded with an outcome outside the ladder (passed_but_nonzero_exit); 123 dropped G_i pair(s); 3 kill-complete pass(es) had one; 1290 crash kill(s)
- coreshop/th: 6 instance(s) outside the benchmark 1.1 population (scored, counted in no measure); 1 instance(s) excluded with an outcome outside the ladder (passed_but_nonzero_exit)
- e-petitions/th: none
- kapua/th: 8 dropped G_i pair(s); 0 kill-complete pass(es) had one
- prestashop/th: 2 instance(s) excluded for harness infrastructure failures; 2 dropped G_i pair(s); 0 kill-complete pass(es) had one
- python-docx/th: none
- sylius/th: 8 instance(s) outside the benchmark 1.1 population (scored, counted in no measure)

## Scoring rules

- algorand-sdk: single_observation family, candidate timeout = drop, crash kill = false
- coddy-agent: single_observation family, candidate timeout = drop, crash kill = true
- coreshop: single_observation family, candidate timeout = drop, crash kill = false; host-dependent mutants disclosed: 96e02276fdb04ae5; nondeterministic mutants excluded from G_i: 2ad72862f21752d7, 96e02276fdb04ae5
- e-petitions: native family, candidate timeout = kill, crash kill = false
- kapua: native family, candidate timeout = kill, crash kill = false; host-dependent mutants disclosed: 42fa6d40e22a43a1
- prestashop: native family, candidate timeout = kill, crash kill = false; host-dependent mutants disclosed: 856b05bc46ec63d9, 8e08150ac4bed473
- python-docx: single_observation family, candidate timeout = drop, crash kill = false
- sylius: single_observation family, candidate timeout = drop, crash kill = false
