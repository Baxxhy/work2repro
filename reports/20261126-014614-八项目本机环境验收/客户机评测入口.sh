#!/bin/bash
set -eu
umask 077
. "$HOME/venv/bin/activate"
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"
export TMPDIR="$XDG_RUNTIME_DIR/req2test-temp"
mkdir -p "$TMPDIR"
chmod 700 "$TMPDIR"
case "${1:-}" in
  evaluate|validate)
    has_host=0
    for arg in "$@"; do
      case "$arg" in --docker-host|--docker-host=*) has_host=1;; esac
    done
    if test "$has_host" = 0; then set -- "$@" --docker-host "$DOCKER_HOST"; fi
    ;;
esac
exec python "$HOME/setup/accept-all/coddy-local.py" "$@"
