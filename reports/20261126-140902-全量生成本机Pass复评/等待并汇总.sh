#!/bin/bash
set -eu
cd "$(dirname "$0")"
while ! ssh -o ConnectTimeout=15 -F /root/lby-docker/req2test-vm/ssh-config req2test-kvm 'for p in algorand-sdk coddy-agent coreshop e-petitions kapua prestashop python-docx sylius; do test "$(cat ~/reeval/medium-th-2051-20261126-140902/logs/$p.exit 2>/dev/null)" = 0 && test -s ~/.req2test/runs/medium-local-exec-20261126-140902-$p/summary.json || exit 1; done'; do
    sleep 60
done
exec bash 汇集客户机结果.sh
