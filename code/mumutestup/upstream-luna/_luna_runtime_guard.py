"""Stop a batch when its local model adapter has a terminal failure."""
import os
from pathlib import Path


class LunaBackendFatal(BaseException):
    # Intentional control-flow exception: upstream catches Exception and otherwise
    # turns model-service failures into empty generated tests.
    pass


def check_luna_fatal():
    marker = os.getenv("MUMU_LLM_FATAL_FILE")
    if marker and Path(marker).is_file():
        raise LunaBackendFatal("Model adapter is unavailable; see the run's backend fatal marker")
