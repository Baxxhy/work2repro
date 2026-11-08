#!/usr/bin/env bash
# Source this file. It configures a local Codex text adapter, not a paid API key.
source /root/Baxxhy/work2/reproductions/mumutestup/deployment/runtime.sh

export MUMU_LUNA_OUTPUT="${MUMU_LUNA_OUTPUT:-$MUMU_ROOT/runs/luna20-20261104}"
export MUMU_LUNA_UPSTREAM="$MUMU_ROOT/upstream-luna"
export MUMU_LUNA_BRIDGE_URL="${MUMU_LUNA_BRIDGE_URL:-http://127.0.0.1:8012/v1}"
export MUMU_LLM_FATAL_FILE="${MUMU_LLM_FATAL_FILE:-$MUMU_LUNA_OUTPUT/bridge-fatal.json}"
export MUMU_LLM_BACKEND=codex-app-server-text-adapter
export MUMU_LUNA_REASONING_EFFORT=medium
export MUMU_LUNA_SPEED=standard

export LLM_PROVIDER=openai
export LLM_MODEL=gpt-6-luna
export LLM_API_URL="${MUMU_LUNA_BRIDGE_URL%/}/chat/completions"
export LLM_API_KEY=local-luna-adapter
# Config() parses a number during initialization. The isolated Luna source then
# sets the effective temperature to None, and neither chat client sends it.
export LLM_TEMPERATURE=0
export LLM_TIMEOUT="${MUMU_LUNA_REQUEST_TIMEOUT:-900}"
export LLM_MAX_RETRIES=2
export OPENAI_BASE_URL="${MUMU_LUNA_BRIDGE_URL%/}"
export OPENAI_API_KEY=local-luna-adapter
unset LLM_MAX_TOKENS LLM_ENABLE_THINKING CODEX_API_KEY

export MUMU_EMBEDDING_BASE_URL=http://127.0.0.1:8001/v1
export MUMU_EMBEDDING_MODEL=all-MiniLM-L6-v2
export MUMU_EMBEDDING_API_KEY=local
export MUMU_MAX_ITERATIONS=4
export MUMU_LOGS_DIR="$MUMU_LUNA_OUTPUT/sample-logs"
export MUMU_REPORTS_DIR="$MUMU_LUNA_OUTPUT/reports"
export MUMU_INDEX_DIR="$MUMU_LUNA_OUTPUT/index_data"
export MUMU_FRAMEWORK_LOG="$MUMU_LUNA_OUTPUT/preflight-framework.log"

# This is the verified proxy available on 4x3090. The retired Qwen runtime's
# old 7894 tunnel is not required for new Luna launches.
export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890
export ALL_PROXY=http://127.0.0.1:7890 all_proxy=http://127.0.0.1:7890
export MAVEN_OPTS='-Xmx2g -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7890 -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7890 -Dhttp.nonProxyHosts=localhost|127.0.0.1'
export MAVEN_ARGS="-s $MUMU_ROOT/deployment/maven-settings-luna.xml"

# Retain the user's existing Docker daemon and persistent storage selection.
export DOCKER_HOST=unix:///run/mutate-docker.sock
