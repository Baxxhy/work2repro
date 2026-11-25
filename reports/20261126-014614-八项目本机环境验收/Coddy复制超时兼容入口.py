"""Run the pinned CLI with a bounded staging timeout for the local Coddy worker."""
import sys
from pathlib import Path
from functools import wraps

import req2test
from req2test.cli import main

engine = Path(req2test.__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(engine))
from r2t.go.execution import ExecutionCopy

checked = ExecutionCopy._checked

@wraps(checked)
def checked_with_copy_budget(self, verb, *args, timeout=30, input=None):
    if verb == "copy-reference":
        timeout = min(120, self._remaining([verb]))
    return checked(self, verb, *args, timeout=timeout, input=input)

if __name__ == "__main__":
    ExecutionCopy._checked = checked_with_copy_budget
    sys.exit(main())
