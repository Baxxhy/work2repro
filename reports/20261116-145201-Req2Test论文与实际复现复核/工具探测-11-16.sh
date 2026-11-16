#!/bin/bash
set -u
cat > audit-prompt.txt
printf "AUDIT_NO_MODEL_CALLS\n"
cd repo
if [ -f pom.xml ]; then
 /bin/bash -lc 'command -v mvn; mvn -version'
elif [ -f composer.json ]; then
 /bin/bash -lc 'command -v php; php --version'
else
 /bin/bash -lc 'command -v python3; python3 -c "import docx; print(123)"'
fi
status=$?
printf "PROBE_EXIT %s\n" "$status"
exit "$status"
