export TU_ROOT=/root/Baxxhy/work2/reproductions/testupdater
export PATH="$TU_ROOT/.venv/bin:/root/Baxxhy/work2/reproductions/mumutestup/toolchains/jdk17/bin:$PATH"
export JAVA_HOME=/root/Baxxhy/work2/reproductions/mumutestup/toolchains/jdk17
export TU_LLM_URL=http://127.0.0.1:8013/v1
export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890
export http_proxy=$HTTP_PROXY https_proxy=$HTTPS_PROXY
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
export LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false
export DOCKER_HOST=unix:///run/mutate-docker.sock
