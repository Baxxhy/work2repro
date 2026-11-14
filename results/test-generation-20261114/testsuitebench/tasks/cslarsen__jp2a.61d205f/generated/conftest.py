import os
import tempfile

import pytest
from PIL import Image

EXE = "/workspace/executable"


@pytest.fixture
def jpeg(tmp_path):
    """4x3 grayscale reference image with controlled pixel levels."""
    path = tmp_path / "sample-é-test.jpg"
    im = Image.new("L", (4, 3))
    im.putdata([0, 32, 96, 255, 16, 64, 128, 240, 8, 80, 160, 224])
    im.save(path, format="JPEG", quality=100, subsampling=0)
    return str(path)


@pytest.fixture
def rgb_jpeg(tmp_path):
    path = tmp_path / "rgb.jpg"
    im = Image.new("RGB", (2, 2))
    im.putdata([(255, 0, 0), (0, 255, 0), (255, 0, 0), (0, 255, 0)])
    im.save(path, format="JPEG", quality=100, subsampling=0)
    return str(path)
