#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
config=/root/lby-docker/req2test-vm/ssh-config
mkdir -p 本机评分
for p in algorand-sdk coddy-agent coreshop e-petitions kapua prestashop python-docx sylius; do
  mkdir -p "本机评分/$p"
  run=".req2test/runs/medium-local-exec-20261126-140902-$p"
  scp -q -F "$config" "req2test-kvm:$run/$p/th/instances.jsonl" "本机评分/$p/instances.jsonl"
  scp -q -F "$config" "req2test-kvm:$run/summary.json" "本机评分/$p/summary.json"
done
source /root/Baxxhy/work2/reproductions/req2test/env.sh
python 同口径核对.py
