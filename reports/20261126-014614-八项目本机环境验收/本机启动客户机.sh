#!/bin/bash
set -eu
cd /root/lby-docker/req2test-vm
exec 9>start.lock
flock -x 9
if ssh -o ConnectTimeout=2 -F ssh-config req2test-kvm true 2>/dev/null; then
  echo 'Req2Test 客户机已运行'
  exit 0
fi
qemu-system-x86_64 -enable-kvm -cpu host -smp 8 -m 24576 \
  -drive file=guest.qcow2,if=virtio,format=qcow2 \
  -drive file=seed.iso,if=virtio,format=raw,readonly=on \
  -netdev user,id=net0,hostfwd=tcp:127.0.0.1:22371-:22 \
  -device virtio-net-pci,netdev=net0 -display none -monitor none \
  -serial file:serial.log -pidfile qemu.pid -daemonize 9>&-
