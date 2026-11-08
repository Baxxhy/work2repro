#!/usr/bin/env bash
export MUMU_ROOT=/root/Baxxhy/work2/reproductions/mumutestup
export MUMU_REPOS_DIR="$MUMU_ROOT/repos"
export MUMU_MAVEN_HOME="$MUMU_ROOT/toolchains/maven"
export MUMU_MAVEN_REPO_BASE="$MUMU_ROOT/maven-repositories"
export MUMU_JAVA_HOME_8="$MUMU_ROOT/toolchains/jdk8"
export MUMU_JAVA_HOME_11="$MUMU_ROOT/toolchains/jdk11"
export MUMU_JAVA_HOME_17="$MUMU_ROOT/toolchains/jdk17"
export MUMU_JAVA_HOME_21="$MUMU_ROOT/toolchains/jdk21"
export MUMU_LOGS_DIR="$MUMU_ROOT/logs"
export MUMU_REPORTS_DIR="$MUMU_ROOT/reports"
export JAVA_HOME="$MUMU_JAVA_HOME_17"
export PATH="$MUMU_ROOT/.venv/bin:$JAVA_HOME/bin:$MUMU_MAVEN_HOME/bin:$PATH"
export LLM_PROVIDER=openai LLM_API_URL=http://127.0.0.1:8000/v1/chat/completions LLM_MODEL=qwen3.5-27b LLM_API_KEY=local LLM_TEMPERATURE=0 LLM_MAX_TOKENS=8192 LLM_ENABLE_THINKING=0
export MUMU_EMBEDDING_BASE_URL=http://127.0.0.1:8001/v1 MUMU_EMBEDDING_MODEL=all-MiniLM-L6-v2 MUMU_EMBEDDING_API_KEY=local MUMU_MAX_ITERATIONS=4
export HTTP_PROXY=http://127.0.0.1:7894 HTTPS_PROXY=http://127.0.0.1:7894 http_proxy=http://127.0.0.1:7894 https_proxy=http://127.0.0.1:7894
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 ANONYMIZED_TELEMETRY=False
# Maven's JVM does not use HTTP_PROXY; these settings are scoped to this task.
export MAVEN_OPTS='-Xmx2g -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7894 -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7894 -Dhttp.nonProxyHosts=localhost|127.0.0.1'

# Maven Resolver requires an explicit Maven proxy, not only JVM proxy properties.
export MAVEN_ARGS="-s $MUMU_ROOT/deployment/maven-settings.xml"
# Compatibility for the author's legacy IndexerConfig.from_env; all endpoints remain local.
export OPENAI_API_KEY=local OPENAI_BASE_URL=http://127.0.0.1:8000/v1
# Any Docker-based project tests must use the user's existing persistent-storage service.
export DOCKER_HOST=unix:///run/mutate-docker.sock
